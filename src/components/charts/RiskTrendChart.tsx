import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TrendPoint } from '../../data/types'
import { GRAPH } from '../../lib/utils'
import { TooltipShell } from './ChartTooltip'

export function RiskTrendChart({ data, height = 240 }: { data: TrendPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="anomalyFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GRAPH.primary} stopOpacity={0.45} />
            <stop offset="55%" stopColor={GRAPH.primary} stopOpacity={0.12} />
            <stop offset="100%" stopColor={GRAPH.primary} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="riskStroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={GRAPH.secondary} />
            <stop offset="100%" stopColor={GRAPH.alert} />
          </linearGradient>
        </defs>

        <CartesianGrid stroke={GRAPH.grid} strokeDasharray="3 5" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: GRAPH.tick, fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: GRAPH.axis }}
          interval="preserveStartEnd"
          minTickGap={18}
        />
        <YAxis
          yAxisId="left"
          tick={{ fill: GRAPH.tick, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          width={42}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={{ fill: GRAPH.tick, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          width={30}
        />
        <Tooltip
          cursor={{ stroke: GRAPH.primary, strokeOpacity: 0.35, strokeDasharray: '3 3' }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            const p = payload[0].payload as TrendPoint
            return (
              <TooltipShell
                title={String(label)}
                rows={[
                  { label: 'Anomalies', value: p.anomalies, color: GRAPH.primary },
                  { label: 'Mean risk', value: p.meanRisk.toFixed(1), color: GRAPH.secondary },
                  { label: 'Baseline', value: p.baseline.toFixed(1), color: GRAPH.neutral },
                ]}
              />
            )
          }}
        />
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="anomalies"
          stroke={GRAPH.primary}
          strokeWidth={1.8}
          fill="url(#anomalyFill)"
          activeDot={{ r: 3, fill: GRAPH.primary, stroke: '#000000', strokeWidth: 2 }}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="meanRisk"
          stroke="url(#riskStroke)"
          strokeWidth={2.2}
          dot={false}
          activeDot={{ r: 3.5, fill: GRAPH.alert, stroke: '#000000', strokeWidth: 2 }}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="baseline"
          stroke={GRAPH.neutral}
          strokeWidth={1.2}
          strokeDasharray="4 4"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
