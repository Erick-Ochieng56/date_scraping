import { cn } from '@/lib/utils'

type StatusKind = 'run' | 'crawl' | 'prospect' | 'lead' | 'generic'

const VARIANTS: Record<string, string> = {
  running: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  crawling: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  pending: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300',
  success: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  failed: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  new: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
  contacted: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
  converted: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  interested: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  synced: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  rejected: 'bg-muted text-muted-foreground',
  generating: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  searching: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  done: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
}

type StatusBadgeProps = {
  status: string
  kind?: StatusKind
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status.toLowerCase()
  const variant = VARIANTS[key] ?? 'bg-muted text-muted-foreground'

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium capitalize',
        variant,
        className
      )}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}
