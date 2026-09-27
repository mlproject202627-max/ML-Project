/**
 * Real-time browser telemetry for Sentinel.
 *
 * Captures what a browser can genuinely observe about the signed-in user:
 *  - LOGIN_TIME / LOGOUT_TIME  (with geolocation when the user permits)
 *  - LOCATION_UPDATE           (requested once per session, plus on visibility change)
 *  - FILE_UPLOAD / FILE_DROP   (user moves data through the web app)
 *  - USB_ATTACH                (WebUSB pairings — visible only after user grant)
 *  - VIEW_DWELL                (which view the analyst used and for how long)
 *  - HEARTBEAT                 (session liveness, keeps last_seen fresh)
 *
 * Events are buffered and flushed every 10s (and on page hide) to
 * POST /api/v1/telemetry/browser. Failures are silent — telemetry must
 * never break the product.
 */
import { useEffect, useRef } from 'react'
import { getAccessToken } from './api'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const FLUSH_INTERVAL_MS = 10_000

type TelemetryEventType =
  | 'LOGIN_TIME' | 'LOGOUT_TIME' | 'LOCATION_UPDATE' | 'USB_ATTACH'
  | 'USB_ACCESS' | 'FILE_UPLOAD' | 'FILE_DROP' | 'DATA_ACCESS'
  | 'VIEW_DWELL' | 'HEARTBEAT'

interface TelemetryEvent {
  event_type: TelemetryEventType
  occurred_at: string
  source: 'browser'
  ip_address?: string
  location?: string
  latitude?: string
  longitude?: string
  accuracy_m?: number
  device?: string
  resource?: string
  application?: string
  metadata?: Record<string, unknown>
}

const buffer: TelemetryEvent[] = []
let flushTimer: number | null = null
let heartbeatTimer: number | null = null
let activeView: { view: string; since: number } | null = null
let started = false

function nowIso(): string {
  return new Date().toISOString()
}

function track(event: TelemetryEvent) {
  buffer.push(event)
  // Keep the buffer bounded if the API is unreachable for a long time
  if (buffer.length > 500) buffer.splice(0, buffer.length - 500)
}

async function flush(): Promise<void> {
  if (buffer.length === 0 || !getAccessToken()) return
  const events = buffer.splice(0, buffer.length)
  try {
    await fetch(`${API_BASE}/api/v1/telemetry/browser`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: JSON.stringify({ events }),
      // keepalive so LOGOUT_TIME survives page unload
      keepalive: true,
    })
  } catch {
    // Telemetry is best-effort by design; drop on failure.
  }
}

/* ---------------- geolocation (only with user permission) ---------------- */

function requestLocation(reason: string): void {
  if (!('geolocation' in navigator)) return
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      track({
        event_type: 'LOCATION_UPDATE',
        occurred_at: nowIso(),
        source: 'browser',
        latitude: pos.coords.latitude.toFixed(6),
        longitude: pos.coords.longitude.toFixed(6),
        accuracy_m: pos.coords.accuracy,
        metadata: { reason },
      })
    },
    (err) => {
      // Record that location was requested but not granted — still a signal
      track({
        event_type: 'LOCATION_UPDATE',
        occurred_at: nowIso(),
        source: 'browser',
        latitude: 'denied',
        metadata: { reason, denied: true, code: err.code },
      })
    },
    { timeout: 10_000, maximumAge: 300_000 },
  )
}

/* ----------------------------- WebUSB hook ------------------------------ */

async function watchUsbPairings(): Promise<void> {
  const nav = navigator as Navigator & {
    usb?: {
      addEventListener: (type: string, cb: (e: Event) => void) => void
    }
  }
  if (!nav.usb) return
  nav.usb.addEventListener('connect', (e: Event) => {
    const device = (e as unknown as { device?: { productName?: string; vendorId?: number; productId?: number } }).device
    track({
      event_type: 'USB_ATTACH',
      occurred_at: nowIso(),
      source: 'browser',
      device: device?.productName || `usb:${device?.vendorId ?? '?'}/${device?.productId ?? '?'}`,
      metadata: { via: 'webusb', vendorId: device?.vendorId, productId: device?.productId },
    })
  })
}

/* --------------------------- public attach API --------------------------- */

/** Call once after a successful login. Records the login moment + geo. */
export function trackLogin(): void {
  track({ event_type: 'LOGIN_TIME', occurred_at: nowIso(), source: 'browser' })
  requestLocation('login')
  startTelemetry()
}

/** Call on explicit logout. Fires a best-effort LOGOUT_TIME event. */
export function trackLogout(): void {
  track({ event_type: 'LOGOUT_TIME', occurred_at: nowIso(), source: 'browser' })
  void flush()
  stopTelemetry()
}

/** Report a file the user pushed into or pulled out of the web app. */
export function trackFileTransfer(kind: 'FILE_UPLOAD' | 'FILE_DROP', file: { name: string; size: number; type?: string }): void {
  track({
    event_type: kind,
    occurred_at: nowIso(),
    source: 'browser',
    resource: file.name,
    metadata: { size: file.size, mime: file.type ?? null },
  })
}

/** Report sensitive data the user viewed (used by drawers showing user detail). */
export function trackDataAccess(resource: string, metadata?: Record<string, unknown>): void {
  track({ event_type: 'DATA_ACCESS', occurred_at: nowIso(), source: 'browser', resource, metadata })
}

/* ------------------------------ lifecycle ------------------------------- */

function onVisibilityChange(): void {
  if (document.visibilityState === 'hidden') {
    if (activeView) {
      track({
        event_type: 'VIEW_DWELL',
        occurred_at: nowIso(),
        source: 'browser',
        resource: activeView.view,
        metadata: { seconds: Math.round((Date.now() - activeView.since) / 1000) },
      })
      activeView = null
    }
    void flush()
  }
}

/* ------------------- document-level file transfer hooks ------------------ */

function onDocumentDrop(e: DragEvent): void {
  const file = e.dataTransfer?.files?.[0]
  if (file) trackFileTransfer('FILE_DROP', file)
}

function onDocumentChange(e: Event): void {
  const target = e.target as HTMLInputElement | null
  if (target && target.type === 'file' && target.files?.[0]) {
    trackFileTransfer('FILE_UPLOAD', target.files[0])
  }
}

function startTelemetry(): void {
  if (started) return
  started = true

  flushTimer = window.setInterval(flush, FLUSH_INTERVAL_MS)
  heartbeatTimer = window.setInterval(() => {
    track({ event_type: 'HEARTBEAT', occurred_at: nowIso(), source: 'browser' })
  }, 60_000)

  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('pagehide', flush)
  document.addEventListener('drop', onDocumentDrop)
  document.addEventListener('change', onDocumentChange)
  void watchUsbPairings()
}

function stopTelemetry(): void {
  if (!started) return
  started = false
  if (flushTimer !== null) window.clearInterval(flushTimer)
  if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
  flushTimer = null
  heartbeatTimer = null
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('pagehide', flush)
  document.removeEventListener('drop', onDocumentDrop)
  document.removeEventListener('change', onDocumentChange)
}

/**
 * useTelemetry — mounts inside the authenticated app shell.
 * Tracks view dwell time per route change and keeps the session warm.
 */
export function useTelemetry(view: string): void {
  const viewRef = useRef(view)

  useEffect(() => {
    // Close out the previous view's dwell event
    if (activeView && activeView.view !== viewRef.current) {
      const seconds = Math.round((Date.now() - activeView.since) / 1000)
      track({
        event_type: 'VIEW_DWELL',
        occurred_at: nowIso(),
        source: 'browser',
        resource: activeView.view,
        metadata: { seconds },
      })
    }
    activeView = { view, since: Date.now() }
    viewRef.current = view
  }, [view])

  useEffect(() => {
    return () => {
      if (activeView) {
        const seconds = Math.round((Date.now() - activeView.since) / 1000)
        track({
          event_type: 'VIEW_DWELL',
          occurred_at: nowIso(),
          source: 'browser',
          resource: activeView.view,
          metadata: { seconds },
        })
        activeView = null
      }
      void flush()
    }
  }, [])
}
