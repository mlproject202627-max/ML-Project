import { riskTone } from '../../lib/utils'

export function RiskDial({
  score,
  size = 68,
  stroke = 6,
  label,
  sublabel,
}: {
  score: number
  size?: number
  stroke?: number
  label?: string
  sublabel?: string
}) {
  const tone = riskTone(score)
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const progress = Math.max(0, Math.min(100, score)) / 100
  const gid = `dial-${tone.label}-${size}-${Math.round(score)}`

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={tone.hex} stopOpacity="0.55" />
            <stop offset="100%" stopColor={tone.hex} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#252a30"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={`url(#${gid})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
          style={{
            transition: 'stroke-dashoffset 700ms cubic-bezier(0.22,1,0.36,1)',
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="num font-semibold leading-none"
          style={{ fontSize: size * 0.3, color: tone.hex }}
        >
          {label ?? Math.round(score)}
        </span>
        {sublabel && (
          <span className="mt-0.5 text-[9px] tracking-[0.14em] text-faint uppercase">
            {sublabel}
          </span>
        )}
      </div>
    </div>
  )
}
