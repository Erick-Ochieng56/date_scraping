import { cn } from '@/lib/utils'

type ScoreBadgeProps = {
  score: number | null | undefined
  label?: string | null
  className?: string
}

const LABEL_VARIANTS: Record<string, string> = {
  high: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  medium: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300',
  low: 'bg-muted text-muted-foreground',
}

export function ScoreBadge({ score, label, className }: ScoreBadgeProps) {
  if (score == null) {
    return <span className={cn('text-sm text-muted-foreground', className)}>—</span>
  }

  const key = (label ?? '').toLowerCase()
  const variant = LABEL_VARIANTS[key] ?? 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium tabular-nums',
        variant,
        className
      )}
      title={label ? `${score} (${label})` : String(score)}
    >
      {score}
      {label ? <span className="font-normal opacity-80">· {label}</span> : null}
    </span>
  )
}
