import type { Department } from '../../data/types'
import { cn, deptShade } from '../../lib/utils'

/**
 * Monochrome identity chip. Departments stay distinguishable by grey
 * value rather than hue, so the chrome never introduces colour.
 */
export function Avatar({
  initials,
  department,
  size = 34,
  className,
  ring,
}: {
  initials: string
  department?: Department
  size?: number
  className?: string
  /** Hex white/grey for the outer ring — signals risk without colour. */
  ring?: string
}) {
  const shade = department ? deptShade(department) : 18
  const top = shade + 8
  const bottom = Math.max(5, shade - 5)

  return (
    <span
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center rounded-[10px] font-semibold',
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        color: '#f5f7fa',
        background: `linear-gradient(150deg, hsl(0 0% ${top}%), hsl(0 0% ${bottom}%))`,
        boxShadow: ring
          ? `0 0 0 1px ${ring}80`
          : `0 0 0 1px rgba(255, 255, 255, 0.1)`,
      }}
    >
      {initials}
    </span>
  )
}
