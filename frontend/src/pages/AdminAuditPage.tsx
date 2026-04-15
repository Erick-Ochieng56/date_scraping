import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function AdminAuditPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-foreground">Audit log</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Immutable admin/staff action timeline with filtering by actor, action type, and object.
      </p>
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        Next implementation slice: paginated audit table + export to CSV for compliance reviews.
      </div>
      <Button variant="outline" asChild>
        <Link to="/admin">Back to admin home</Link>
      </Button>
    </div>
  )
}
