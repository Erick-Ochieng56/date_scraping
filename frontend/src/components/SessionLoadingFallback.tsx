import { Loader2 } from 'lucide-react'

/** Full-screen while auth bootstrap runs (before route layouts mount). */
export function SessionLoadingFallback() {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 className="size-10 animate-spin text-primary" aria-hidden />
      <div className="flex w-56 max-w-full gap-2" aria-hidden>
        <div className="h-1.5 flex-1 rounded-full bg-muted motion-safe:animate-pulse" />
        <div className="h-1.5 flex-1 rounded-full bg-muted motion-safe:animate-pulse motion-safe:[animation-delay:120ms]" />
        <div className="h-1.5 flex-1 rounded-full bg-muted motion-safe:animate-pulse motion-safe:[animation-delay:240ms]" />
      </div>
      <span className="sr-only">Loading session</span>
    </div>
  )
}
