import { cn } from '@/lib/utils'

/**
 * Standard page header: just the main title, with an optional action slot on
 * the right. `eyebrow` / `description` are accepted for backwards compatibility
 * but no longer rendered (pages show only the title, per design direction).
 */
export function PageHeader({
  title,
  action,
  className,
}: {
  eyebrow?: React.ReactNode
  title: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        {/* eyebrow + description are intentionally not rendered — pages show
            only the main title (per design direction). Props kept optional so
            existing call sites don't need to change. */}
        <h1 className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">
          {title}
        </h1>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
