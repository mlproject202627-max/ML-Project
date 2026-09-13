import { ShieldCheck } from 'lucide-react'
import { summary } from '../../data/mock'
import { Meter } from '../ui/Meter'

export function PostureWidget() {
  const score = 72
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold tracking-[0.13em] text-faint uppercase">
          Posture
        </span>
        <ShieldCheck className="size-3.5 text-white/60" />
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="num text-[20px] leading-none font-semibold text-white">{score}</span>
        <span className="text-[10px] text-faint">/100</span>
        <span className="num ml-auto text-[10px] text-[#fde68a]">elevated</span>
      </div>
      <Meter value={score} color="#fde68a" height={4} className="mt-2.5" />
      <dl className="mt-2.5 grid grid-cols-2 gap-x-2 gap-y-1.5 text-[10px]">
        <div>
          <dt className="text-faint">Coverage</dt>
          <dd className="num text-fg">{summary.coverage}%</dd>
        </div>
        <div>
          <dt className="text-faint">False +ve</dt>
          <dd className="num text-fg">{summary.falsePositiveRate}%</dd>
        </div>
      </dl>
    </div>
  )
}
