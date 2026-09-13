import { useState } from 'react'
import { Bell, Database, Fingerprint, ShieldCheck, Sliders, Trash2 } from 'lucide-react'
import { detectors, employees } from '../../data/mock'
import { Avatar } from '../ui/Avatar'
import { Panel } from '../ui/Panel'
import { Segmented } from '../ui/Segmented'
import { Slider, Toggle } from '../ui/Controls'
import { riskTone } from '../../lib/utils'

export function Settings() {
  const [threshold, setThreshold] = useState(65)
  const [offHoursWeight, setOffHoursWeight] = useState(72)
  const [peerWeight, setPeerWeight] = useState(58)
  const [minConfidence, setMinConfidence] = useState(70)
  const [dedupeWindow, setDedupeWindow] = useState(15)
  const [retention, setRetention] = useState<'90d' | '1y' | '3y' | '7y'>('1y')

  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(detectors.map((d) => [d.name, d.status !== 'training'])),
  )

  const [channels, setChannels] = useState({
    siem: true,
    slack: true,
    email: false,
    pagerduty: true,
    webhook: false,
  })

  const [policy, setPolicy] = useState({
    pseudonymise: true,
    justifiedAccess: true,
    autoContain: false,
    legalHold: true,
  })

  const [watchlist, setWatchlist] = useState(
    employees.filter((e) => e.status === 'watchlist').map((e) => e.id),
  )

  const watched = employees.filter((e) => watchlist.includes(e.id))

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div className="mb-2">
        <h1 className="text-[20px] font-bold text-[var(--color-text)]">Detection Policies</h1>
        <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
          Configure how Sentinel identifies and prioritizes suspicious behaviour.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Detection sensitivity"
          subtitle="Tune the ensemble's decision boundary. Changes take effect on the next scoring cycle."
          actions={<span className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]"><Sliders className="size-3" /> live</span>}
        >
          <div className="divide-y divide-[var(--color-border)]">
            <Slider label="Global alert threshold" value={threshold} onChange={setThreshold} unit="/100" hint="Composite risk above this value raises an alert." />
            <Slider label="Off-hours weight" value={offHoursWeight} onChange={setOffHoursWeight} unit="%" hint="How strongly activity inside 22:00–06:00 contributes to the anomaly score." />
            <Slider label="Peer deviation weight" value={peerWeight} onChange={setPeerWeight} unit="%" hint="Weight applied to distance from the peer-group centroid." />
            <Slider label="Minimum model confidence" value={minConfidence} onChange={setMinConfidence} unit="%" hint="Detections below this confidence are logged but kept out of the triage queue." />
            <Slider label="Alert de-duplication window" value={dedupeWindow} onChange={setDedupeWindow} min={5} max={120} step={5} unit=" min" hint="Repeat detections inside this window collapse into one case." />
          </div>
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Active detectors" subtitle="Disabling a detector removes it from the ensemble immediately">
            <div className="divide-y divide-[var(--color-border)]">
              {detectors.map((d) => (
                <Toggle
                  key={d.name}
                  label={d.name}
                  description={`${d.family} · F1 ${d.f1.toFixed(3)} · drift ${d.drift.toFixed(2)}`}
                  checked={enabled[d.name] ?? false}
                  onChange={(v) => setEnabled((s) => ({ ...s, [d.name]: v }))}
                  accent={d.status === 'degraded' ? '#D97706' : 'var(--color-primary)'}
                />
              ))}
            </div>
          </Panel>

          <Panel title="Alert routing" subtitle="Where confirmed detections are delivered" actions={<Bell className="size-3.5 text-[var(--color-text-faint)]" />}>
            <div className="divide-y divide-[var(--color-border)]">
              <Toggle label="SIEM forwarder" description="Push normalised events to the enterprise SIEM." checked={channels.siem} onChange={(v) => setChannels((s) => ({ ...s, siem: v }))} />
              <Toggle label="SOC Slack channel" description="#soc-insider-threat, critical and high only." checked={channels.slack} onChange={(v) => setChannels((s) => ({ ...s, slack: v }))} />
              <Toggle label="Email digest" description="Hourly rollup to the threat-hunting distribution list." checked={channels.email} onChange={(v) => setChannels((s) => ({ ...s, email: v }))} />
              <Toggle label="PagerDuty on-call" description="Page the on-call analyst for critical severity." checked={channels.pagerduty} onChange={(v) => setChannels((s) => ({ ...s, pagerduty: v }))} />
              <Toggle label="Outbound webhook" description="POST the full case payload to a custom endpoint." checked={channels.webhook} onChange={(v) => setChannels((s) => ({ ...s, webhook: v }))} />
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Watchlist"
          subtitle={`${watched.length} identities under enhanced monitoring`}
          padded={false}
        >
          {watched.length === 0 ? (
            <p className="px-4 py-12 text-center text-[12px] text-[var(--color-text-faint)]">No identities on the watchlist.</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {watched.map((e) => {
                const tone = riskTone(e.riskScore)
                return (
                  <li key={e.id} className="flex items-center gap-3 px-3.5 py-2.5 transition-colors duration-150 hover:bg-[var(--color-hover)]">
                    <Avatar initials={e.initials} department={e.department} size={32} ring={tone.hex} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-[var(--color-text)]">{e.name}</p>
                      <p className="truncate text-[10px] text-[var(--color-text-faint)]">
                        {e.title} · <span className="num">{e.peerGroup}</span> · <span className="num">{e.drift.toFixed(1)}σ</span>
                      </p>
                    </div>
                    <span className="num shrink-0 text-[13px] font-semibold" style={{ color: tone.hex }}>{e.riskScore}</span>
                    <button
                      type="button"
                      onClick={() => setWatchlist((w) => w.filter((id) => id !== e.id))}
                      title={`Remove ${e.name} from watchlist`}
                      className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-text-faint)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          <div className="flex items-center gap-2 border-t border-[var(--color-border)] px-3.5 py-3">
            <button
              type="button"
              onClick={() => setWatchlist(employees.filter((e) => e.status === 'watchlist').map((e) => e.id))}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-[10.5px] font-medium text-[var(--color-text-muted)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
            >
              Restore suggested watchlist
            </button>
            <span className="text-[10px] text-[var(--color-text-faint)]">Suggested by drift &gt; 3.0σ in the last 24 h</span>
          </div>
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Data governance" subtitle="How monitored activity is stored" actions={<Database className="size-3.5 text-[var(--color-text-faint)]" />}>
            <div className="mb-1 flex items-center justify-between gap-3">
              <span className="text-[11.5px] font-medium text-[var(--color-text)]">Event retention</span>
              <Segmented size="sm" value={retention} onChange={setRetention} options={[{ value: '90d', label: '90D' }, { value: '1y', label: '1Y' }, { value: '3y', label: '3Y' }, { value: '7y', label: '7Y' }]} />
            </div>
            <p className="mb-3 text-[10px] text-[var(--color-text-faint)]">
              Raw access events are retained for {retention === '90d' ? '90 days' : retention === '1y' ? '1 year' : retention === '3y' ? '3 years' : '7 years'} before aggregation.
            </p>
            <div className="divide-y divide-[var(--color-border)] border-t border-[var(--color-border)]">
              <Toggle label="Pseudonymise identity fields" description="Store stable hashes instead of directory names." checked={policy.pseudonymise} onChange={(v) => setPolicy((s) => ({ ...s, pseudonymise: v }))} />
              <Toggle label="Require justification to view" description="Analysts must record a reason before rendering content." checked={policy.justifiedAccess} onChange={(v) => setPolicy((s) => ({ ...s, justifiedAccess: v }))} />
              <Toggle label="Automatic session containment" description="Auto-revoke sessions at critical severity." checked={policy.autoContain} onChange={(v) => setPolicy((s) => ({ ...s, autoContain: v }))} />
              <Toggle label="Legal hold exemption" description="Never act on identities under legal hold." checked={policy.legalHold} onChange={(v) => setPolicy((s) => ({ ...s, legalHold: v }))} />
            </div>
          </Panel>

          <Panel title="Audit" subtitle="Every analyst action is recorded">
            <ul className="space-y-2.5">
              {[
                { who: 'A. Reyes', what: 'Contained session for U-2291', when: '09:44 UTC', icon: ShieldCheck },
                { who: 'A. Reyes', what: 'Opened case ALT-4821', when: '09:41 UTC', icon: ShieldCheck },
                { who: 'system', what: 'Peer baselines retrained', when: '06:00 UTC', icon: Fingerprint },
                { who: 'M. Okafor', what: 'Dismissed ALT-4789 as benign', when: '05:58 UTC', icon: ShieldCheck },
                { who: 'system', what: 'Threshold raised 60 → 65', when: 'Yesterday', icon: Sliders },
              ].map((row, i) => {
                const Icon = row.icon
                return (
                  <li key={i} className="flex items-center gap-3">
                    <span className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-faint)]">
                      <Icon className="size-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[11px] text-[var(--color-text-muted)]">{row.what}</p>
                      <p className="text-[9.5px] text-[var(--color-text-faint)]">{row.who}</p>
                    </div>
                    <span className="num shrink-0 text-[10px] text-[var(--color-text-faint)]">{row.when}</span>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}
