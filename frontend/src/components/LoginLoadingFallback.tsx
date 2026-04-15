import { Loader2 } from 'lucide-react'

/** Full-viewport fallback while the lazy login chunk loads (no app chrome yet). */
export function LoginLoadingFallback() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-background p-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="relative w-full max-w-sm space-y-5 rounded-xl border border-border bg-card p-8 shadow-sm">
        <div className="flex justify-center">
          <Loader2 className="size-9 animate-spin text-primary" aria-hidden />
        </div>
        <div className="space-y-3">
          <div className="h-10 w-full rounded-md bg-muted/80 motion-safe:animate-pulse" />
          <div className="h-10 w-full rounded-md bg-muted/80 motion-safe:animate-pulse" />
          <div className="mx-auto h-10 w-2/3 rounded-md bg-muted/70 motion-safe:animate-pulse" />
        </div>
        <span className="sr-only">Loading sign-in</span>
      </div>
    </div>
  )
}
