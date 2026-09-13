export function Sparkline({
  data,
  color = '#69717a',
  width = 76,
  height = 26,
  fill = true,
}: {
  data: number[]
  color?: string
  width?: number
  height?: number
  fill?: boolean
}) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const step = width / (data.length - 1)
  const points = data.map((d, i) => {
    const x = i * step
    const y = height - ((d - min) / span) * (height - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const id = `spark-${color.replace(/[^a-z0-9]/gi, '')}-${data.length}`

  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && (
        <polygon
          points={`0,${height} ${points.join(' ')} ${width},${height}`}
          fill={`url(#${id})`}
        />
      )}
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
