import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function AdminSettingsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-foreground">Admin settings</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        System-level settings for thresholds, safety toggles, and integration behavior. Superadmin-only changes will be
        enforced server-side.
      </p>
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        Next implementation slice: readonly config panel first, then controlled edits with audit logging.
      </div>
      <Button variant="outline" asChild>
        <Link to="/admin">Back to admin home</Link>
      </Button>
    </div>
  )
}
