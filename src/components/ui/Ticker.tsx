import { Radio } from 'lucide-react'
import { alerts } from '../../data/mock'
import { SEVERITY_HEX } from '../../lib/utils'

export function Ticker({ onSelect }: { onSelect: (id: string) => void }) {
  const items = alerts.slice(0, 9)
  const doubled = [...items, ...items]

  return (
    <div className="relative flex items-center gap-3 overflow-hidden border-b border-line-soft bg-black">
      <div
        aria-hidden
        className="grid-lines pointer-events-none absolute inset-0 [mask-image:linear-gradient(90deg,transparent,black_20%,black_80%,transparent)]"
      />
      <div className="relative z-10 flex shrink-0 items-center gap-1.5 border-r border-line-soft px-3 py-1.5">
        <span className="relative flex size-1.5">
          <span className="animate-pulse-ring absolute inline-flex size-full rounded-full bg-white/60" />
          <span className="relative inline-flex size-1.5 rounded-full bg-white" />
        </span>
        <span className="text-[10px] font-semibold tracking-[0.16em] text-white/70 uppercase">
          Live
        </span>
        <Radio className="size-3 text-white/40" />
      </div>

      <div className="group relative z-10 flex-1 overflow-hidden py-1.5">
        <div className="animate-ticker flex w-max items-center gap-7 group-hover:[animation-play-state:paused]">
          {doubled.map((a, i) => (
            <button
              key={`${a.id}-${i}`}
              type="button"
              onClick={() => onSelect(a.id)}
              className="flex shrink-0 items-center gap-2 text-[11px] whitespace-nowrap text-muted transition-colors duration-150 hover:text-fg"
            >
              <span
                className="size-1.5 shrink-0 rounded-full"
                style={{ background: SEVERITY_HEX[a.severity] }}
              />
              <span className="num text-[10px] text-faint">{a.id}</span>
              <span>{a.headline}</span>
              <span className="num text-[10px]" style={{ color: SEVERITY_HEX[a.severity] }}>
                {a.riskScore}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
