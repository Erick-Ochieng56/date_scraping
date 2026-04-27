import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function AdminMonitoringPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-foreground">Monitoring</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Production monitoring panel will include run failures, sync issues, queue lag, and worker/queue health.
      </p>
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        Next implementation slice: unified incidents table with severity, source, and remediation actions.
      </div>
      <Button variant="outline" asChild>
        <Link to="/admin">Back to admin home</Link>
      </Button>
    </div>
  )
}
