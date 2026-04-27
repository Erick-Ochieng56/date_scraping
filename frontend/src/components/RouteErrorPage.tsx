import { Link, useRouteError, isRouteErrorResponse } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function RouteErrorPage() {
  const error = useRouteError()

  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
    ? error.message
    : String(error)

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-2xl space-y-6 rounded-xl border border-border bg-card p-10 shadow-sm">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">Something went wrong</p>
          <h1 className="text-3xl font-semibold">Unable to load this page</h1>
          <p className="text-sm leading-6 text-muted-foreground">
            The application failed while loading this route. You can reload the page or go back to the dashboard.
          </p>
        </div>

        <div className="rounded-xl bg-muted p-4 text-sm text-foreground/90">
          <p className="font-medium">Error details:</p>
          <pre className="mt-2 whitespace-pre-wrap break-words">{message}</pre>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={() => window.location.reload()}>Reload page</Button>
          <Button variant="outline" asChild>
            <Link to="/">Back to dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
