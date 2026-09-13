import { cn } from '../../lib/utils'

export function Toggle({ checked, onChange, label, description, accent = '#ffffff' }: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
  accent?: string
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-2.5">
      <span className="min-w-0">
        <span className="block text-[11.5px] font-medium text-fg">{label}</span>
        {description && <span className="mt-0.5 block text-[10.5px] leading-relaxed text-faint">{description}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative mt-0.5 h-[22px] w-[40px] shrink-0 rounded-full border transition-colors duration-150',
          checked ? 'border-transparent' : 'border-line bg-surface-2',
        )}
        style={checked ? { background: `${accent}22`, boxShadow: `inset 0 0 0 1px ${accent}55` } : undefined}
      >
        <span
          className={cn(
            'absolute top-[2px] size-[16px] rounded-full transition-[left,background] duration-200',
            checked ? 'left-[21px]' : 'left-[2px] bg-faint',
          )}
          style={checked ? { background: accent } : undefined}
        />
      </button>
    </label>
  )
}

export function Slider({ label, value, onChange, min = 0, max = 100, step = 1, unit, hint, accent: _accent = '#ffffff' }: {
  label: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  unit?: string
  hint?: string
  accent?: string
}) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="py-2.5">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-[11.5px] font-medium text-fg">{label}</span>
        <span className="num text-[12px] font-semibold text-fg">
          {value}
          {unit}
        </span>
      </div>
      <div className="relative">
        <div className="h-[4px] w-full overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full rounded-full bg-white/60" style={{ width: `${pct}%` }} />
        </div>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-label={label}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 h-[18px] w-full -translate-y-[6px] cursor-pointer opacity-0"
        />
      </div>
      {hint && <p className="mt-1.5 text-[10px] text-faint">{hint}</p>}
    </div>
  )
}
