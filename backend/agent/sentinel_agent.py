#!/usr/bin/env python3
"""Sentinel endpoint agent — reports real OS-level USB and file-access moments.

What it watches (Linux):
  • USB plug / unplug events           → USB_ATTACH / detach note
  • USB mass-storage mounts            → USB_ACCESS
  • File activity under watched paths  → DATA_ACCESS (created/modified/moved)

Usage:
  cd backend
  venv/bin/python agent/sentinel_agent.py \
      --api http://localhost:8000 \
      --key  sk_live_...            # issued by an admin via POST /api/v1/telemetry/agent-keys
      [--watch ~/Documents /mnt]    # extra directories to watch (default: /media, /mnt, /run/media/$USER)
      [--interval 5]

The agent buffers events and flushes them every --interval seconds.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone

DEFAULT_WATCH_DIRS = ["/media", "/mnt", os.path.expanduser("~/Documents")]
BATCH_FLUSH_SECONDS = 5


class EventBuffer:
    """Thread-safe queue of telemetry events waiting to be posted."""

    def __init__(self) -> None:
        self._events: deque = deque()
        self._lock = threading.Lock()

    def add(self, event_type: str, device: str | None = None,
            resource: str | None = None, metadata: dict | None = None) -> None:
        evt = {
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "source": "agent",
            "device": device,
            "resource": resource,
            "metadata": metadata or {},
        }
        with self._lock:
            self._events.append(evt)
        print(f"  [+] {event_type} {resource or device or ''}")

    def drain(self) -> list:
        with self._lock:
            events, self._events = list(self._events), deque()
        return events


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_udisks() -> str | None:
    from shutil import which
    return which("udisksctl")


def usb_monitor_loop(buffer: EventBuffer) -> None:
    """Watch kernel uevents for USB plug/unplug (works without any deps)."""
    try:
        proc = subprocess.Popen(
            ["stdbuf", "-oL", "udevadm", "monitor", "--kernel", "--subsystem-match=usb"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
    except FileNotFoundError:
        print("  [!] udevadm not found; USB plug events unavailable")
        return

    print("  [✓] watching USB plug events (udevadm)")
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("UDEV  "):
            # Only udev (post-probe) events carry useful device info
            parts = line.split()
            if len(parts) >= 3:
                action, devpath = parts[1], parts[2]
                name = devpath.split("/")[-1]
                if action == "add":
                    buffer.add("USB_ATTACH", device=name, metadata={"devpath": devpath})
                elif action == "remove":
                    buffer.add("USB_ACCESS", device=name,
                               metadata={"action": "detach", "devpath": devpath})


def usb_mount_loop(buffer: EventBuffer, interval: float) -> None:
    """Detect mounted removable filesystems via /proc/mounts (poll every interval)."""
    seen: set[str] = set()
    print("  [✓] watching mounted volumes (/proc/mounts)")
    while True:
        try:
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    dev, mountpoint = parts[0], parts[1]
                    # Removable-media hints: /media, /mnt, /run/media, sd*, sr*
                    if any(hint in mountpoint for hint in ("/media", "/mnt", "/run/media")) or \
                       any(dev.startswith(p) for p in ("/dev/sd", "/dev/sr")):
                        if mountpoint not in seen:
                            seen.add(mountpoint)
                            buffer.add("USB_ACCESS", device=dev, resource=mountpoint,
                                       metadata={"kind": "mount"})
            # Unmounts
            gone = seen - {p.split()[1] for p in
                           [l.split() for l in open("/proc/mounts") if len(l.split()) >= 2]}
            for mountpoint in gone:
                if any(hint in mountpoint for hint in ("/media", "/mnt", "/run/media")):
                    buffer.add("USB_ACCESS", device=None, resource=mountpoint,
                               metadata={"kind": "unmount"})
                    seen.discard(mountpoint)
        except Exception as exc:  # keep the agent alive no matter what
            print(f"  [!] mount poll error: {exc}")
        time.sleep(interval)


def file_watch_loop(buffer: EventBuffer, watch_dirs: list[str], interval: float) -> None:
    """Poll watched directories for created/modified files (no inotify deps)."""
    snapshot: dict[str, float] = {}

    def scan() -> dict[str, float]:
        current: dict[str, float] = {}
        for root_dir in watch_dirs:
            if not os.path.isdir(root_dir):
                continue
            try:
                for dirpath, _dirnames, filenames in os.walk(root_dir):
                    # Skip huge system trees
                    depth = dirpath[len(root_dir):].count(os.sep)
                    if depth >= 3:
                        _dirnames[:] = []
                        continue
                    for fn in filenames:
                        path = os.path.join(dirpath, fn)
                        try:
                            current[path] = os.stat(path).st_mtime
                        except OSError:
                            continue
            except OSError:
                continue
        return current

    print(f"  [✓] watching files under {', '.join(watch_dirs)}")
    snapshot = scan()
    while True:
        time.sleep(max(interval, 10))
        current = scan()
        for path, mtime in current.items():
            if path not in snapshot:
                buffer.add("DATA_ACCESS", resource=path, metadata={"change": "created"})
            elif mtime > snapshot[path]:
                buffer.add("DATA_ACCESS", resource=path, metadata={"change": "modified"})
        for path in snapshot.keys() - current.keys():
            buffer.add("DATA_ACCESS", resource=path, metadata={"change": "deleted"})
        snapshot = current


def flush_loop(buffer: EventBuffer, api_url: str, headers: dict, interval: float) -> None:
    url = f"{api_url.rstrip('/')}/api/v1/telemetry/agent"
    while True:
        time.sleep(interval)
        events = buffer.drain()
        if not events:
            continue
        body = json.dumps({"events": events}).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                print(f"  [→] flushed {result.get('stored', '?')}/{len(events)} events")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:200]
            print(f"  [!] API error {exc.code}: {detail}")
        except Exception as exc:
            print(f"  [!] flush failed ({exc}); events dropped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel endpoint agent")
    parser.add_argument("--api", default=os.environ.get("SENTINEL_API_URL", "http://localhost:8000"))
    parser.add_argument("--key", default=os.environ.get("SENTINEL_AGENT_KEY"),
                        help="agent key (sk_live_...), issued via POST /api/v1/telemetry/agent-keys")
    parser.add_argument("--watch", nargs="*", default=None,
                        help="directories to watch for file activity")
    parser.add_argument("--interval", type=float, default=BATCH_FLUSH_SECONDS,
                        help="seconds between flushes")
    args = parser.parse_args()

    if not args.key:
        print("error: --key or SENTINEL_AGENT_KEY is required (ask an admin to issue one)")
        sys.exit(1)

    watch_dirs = args.watch or DEFAULT_WATCH_DIRS
    buffer = EventBuffer()
    headers = {"Content-Type": "application/json", "X-Agent-Key": args.key}

    print("Sentinel endpoint agent")
    print(f"  api: {args.api}")
    print(f"  watching: {', '.join(watch_dirs)}")

    threads = [
        threading.Thread(target=usb_monitor_loop, args=(buffer,), daemon=True),
        threading.Thread(target=usb_mount_loop, args=(buffer, args.interval), daemon=True),
        threading.Thread(target=file_watch_loop, args=(buffer, watch_dirs, args.interval), daemon=True),
        threading.Thread(target=flush_loop, args=(buffer, args.api, headers, args.interval), daemon=True),
    ]
    for t in threads:
        t.start()

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    print("  agent running — Ctrl+C to stop")
    try:
        while not stop.is_set():
            time.sleep(1)
    finally:
        print("  shutting down")


if __name__ == "__main__":
    main()
