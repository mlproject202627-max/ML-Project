import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { BEHAVIOUR_AXES } from '../../data/mock'
import type { BehaviourVector } from '../../data/types'
import { GRAPH } from '../../lib/utils'
import { TooltipShell } from './ChartTooltip'

export function BehaviourRadar({
  behaviour,
  baseline,
  height = 268,
}: {
  behaviour: BehaviourVector
  /** Peer-group mean for the same axes. */
  baseline: BehaviourVector
  height?: number
}) {
  const data = BEHAVIOUR_AXES.map((axis) => ({
    axis: axis.label,
    user: behaviour[axis.key],
    peer: baseline[axis.key],
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={GRAPH.grid} strokeDasharray="2 4" />
        <PolarAngleAxis dataKey="axis" tick={{ fill: GRAPH.tick, fontSize: 10 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            const user = payload.find((p) => p.dataKey === 'user')?.value as number | undefined
            const peer = payload.find((p) => p.dataKey === 'peer')?.value as number | undefined
            if (user === undefined || peer === undefined) return null
            const delta = user - peer
            return (
              <TooltipShell
                title={String(label)}
                rows={[
                  { label: 'This user', value: user, color: GRAPH.primary },
                  { label: 'Peer mean', value: peer, color: GRAPH.neutral },
                  {
                    label: 'Delta',
                    value: `${delta > 0 ? '+' : ''}${delta}`,
                    color: delta > 25 ? GRAPH.alert : delta > 10 ? GRAPH.tertiary : GRAPH.good,
                  },
                ]}
              />
            )
          }}
        />
        <Radar
          name="Peer mean"
          dataKey="peer"
          stroke={GRAPH.neutral}
          strokeWidth={1.4}
          strokeDasharray="4 4"
          fill={GRAPH.neutral}
          fillOpacity={0.12}
        />
        <Radar
          name="This user"
          dataKey="user"
          stroke={GRAPH.primary}
          strokeWidth={2}
          fill={GRAPH.primary}
          fillOpacity={0.22}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
