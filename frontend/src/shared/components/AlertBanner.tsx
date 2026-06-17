import { cn } from '@/lib/utils'

type AlertBannerProps = {
  message?: string | null
  error?: string | null
  className?: string
}

export function AlertBanner({ message, error, className }: AlertBannerProps) {
  if (!message && !error) return null

  return (
    <div
      className={cn(
        'rounded-lg border px-3 py-2 text-sm',
        error
          ? 'border-destructive/40 bg-destructive/10 text-destructive'
          : 'border-border bg-muted/50 text-foreground',
        className
      )}
      role={error ? 'alert' : 'status'}
    >
      {error ?? message}
    </div>
  )
}
