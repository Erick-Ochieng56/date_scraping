import { Loader2 } from 'lucide-react'

/** Shown in dashboard/admin main while a lazy route chunk loads (sidebar stays mounted). */
export function PageContentSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-3">
        <Loader2 className="size-5 shrink-0 animate-spin text-primary" aria-hidden />
        <div className="h-8 max-w-xs flex-1 rounded-md bg-muted/80 motion-safe:animate-pulse" />
      </div>
      <div className="space-y-3">
        <div className="h-4 w-full rounded bg-muted/60 motion-safe:animate-pulse" />
        <div className="h-4 w-[92%] rounded bg-muted/60 motion-safe:animate-pulse" />
        <div className="h-4 w-[78%] rounded bg-muted/60 motion-safe:animate-pulse" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="h-28 rounded-lg border border-border/50 bg-muted/25 motion-safe:animate-pulse" />
        <div className="h-28 rounded-lg border border-border/50 bg-muted/25 motion-safe:animate-pulse" />
      </div>
      <span className="sr-only">Loading page</span>
    </div>
  )
}
