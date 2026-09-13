import { useState, useCallback } from 'react'
import { ChevronRight } from 'lucide-react'
import { NAV_GROUPS, type ViewId } from '../../lib/nav'
import { cn } from '../../lib/utils'
import { Logomark } from './Logomark'

export function Sidebar({
  active,
  onNavigate,
  collapsed = false,
}: {
  active: ViewId
  onNavigate: (id: ViewId) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}) {
  // Auto-expand the group containing the active item
  const activeGroup = NAV_GROUPS.find((g) => g.items.some((n) => n.id === active))
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(activeGroup ? [activeGroup.id] : [])
  )

  // Update expanded groups when active changes
  if (activeGroup && !expandedGroups.has(activeGroup.id)) {
    setExpandedGroups((prev) => new Set([...prev, activeGroup.id]))
  }

  const toggleGroup = useCallback((groupId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) {
        next.delete(groupId)
      } else {
        next.add(groupId)
      }
      return next
    })
  }, [])

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-[var(--color-border)] bg-[var(--color-card)] transition-all duration-200',
        collapsed ? 'w-[60px]' : 'w-[240px]'
      )}
    >
      {/* Brand */}
      <div className="flex h-[56px] shrink-0 items-center gap-2.5 border-b border-[var(--color-border)] px-4">
        <Logomark size={26} />
        {!collapsed && (
          <div className="min-w-0">
            <span className="block text-[13px] leading-tight font-bold tracking-[0.12em] text-[var(--color-text)]">
              SENTINEL
            </span>
            <span className="block text-[9px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
              Insider Threat UEBA
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => {
          const isExpanded = expandedGroups.has(group.id)
          const hasActiveChild = group.items.some((n) => n.id === active)
          const GroupIcon = group.icon

          // Single-item group (Overview) — render as direct link
          if (group.items.length === 1) {
            const item = group.items[0]
            const ItemIcon = item.icon
            const isActive = item.id === active
            return (
              <button
                key={group.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={cn(
                  'mb-1 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors duration-150',
                  isActive
                    ? 'bg-[var(--color-surface)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]'
                )}
                title={collapsed ? item.label : undefined}
              >
                <span
                  className={cn(
                    'grid size-7 shrink-0 place-items-center rounded-md transition-colors duration-150',
                    isActive
                      ? 'bg-[var(--color-primary)] text-[var(--color-primary-text)]'
                      : 'bg-[var(--color-surface)] text-[var(--color-text-muted)]'
                  )}
                >
                  <ItemIcon className="size-3.5" />
                </span>
                {!collapsed && (
                  <span className="truncate text-[12.5px] font-medium">{item.label}</span>
                )}
              </button>
            )
          }

          // Multi-item group — collapsible
          return (
            <div key={group.id} className="mb-1">
              <button
                type="button"
                onClick={() => toggleGroup(group.id)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors duration-150',
                  hasActiveChild
                    ? 'text-[var(--color-text)]'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]'
                )}
                title={collapsed ? group.label : undefined}
              >
                <span
                  className={cn(
                    'grid size-7 shrink-0 place-items-center rounded-md transition-colors duration-150',
                    hasActiveChild
                      ? 'bg-[var(--color-primary)] text-[var(--color-primary-text)]'
                      : 'bg-[var(--color-surface)] text-[var(--color-text-muted)]'
                  )}
                >
                  <GroupIcon className="size-3.5" />
                </span>
                {!collapsed && (
                  <>
                    <span className="flex-1 truncate text-[12.5px] font-medium">{group.label}</span>
                    <ChevronRight
                      className={cn(
                        'size-3.5 shrink-0 text-[var(--color-text-faint)] transition-transform duration-200',
                        isExpanded && 'rotate-90'
                      )}
                    />
                  </>
                )}
              </button>

              {/* Children */}
              {!collapsed && (
                <div
                  className={cn(
                    'nav-group-children ml-[18px] border-l border-[var(--color-border)] pl-2.5',
                    isExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
                  )}
                >
                  {group.items.map((item) => {
                    const ItemIcon = item.icon
                    const isActive = item.id === active
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => onNavigate(item.id)}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left transition-colors duration-150',
                          isActive
                            ? 'bg-[var(--color-surface)] font-medium text-[var(--color-text)]'
                            : 'text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]'
                        )}
                      >
                        <ItemIcon className="size-3.5 shrink-0" />
                        <span className="truncate text-[12px]">{item.label}</span>
                        {isActive && (
                          <span className="ml-auto size-1.5 shrink-0 rounded-full bg-[var(--color-primary)]" />
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="shrink-0 border-t border-[var(--color-border)] px-3 py-3">
          <p className="text-[9.5px] text-[var(--color-text-faint)]">
            Sentinel UEBA v1.0 · demo build
          </p>
          <p className="text-[9px] text-[var(--color-text-faint)]">
            All data is synthetic
          </p>
        </div>
      )}
    </aside>
  )
}
