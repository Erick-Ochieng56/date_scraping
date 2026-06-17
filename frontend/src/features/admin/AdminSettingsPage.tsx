import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys } from '@/features/admin/queryKeys'
import { fetchAdminSettingsStatus } from '@/shared/api/admin'
import { PageHeader } from '@/shared/components/PageHeader'

function statusBadge(status: string, configured: boolean) {
  if (status === 'ready') return <span className="text-emerald-600">Ready</span>
  if (status === 'disabled') return <span className="text-muted-foreground">Disabled</span>
  if (!configured) return <span className="text-amber-600">Not configured</span>
  return <span className="text-amber-600">Incomplete</span>
}

export function AdminSettingsPage() {
  const settingsQ = useQuery({
    queryKey: adminKeys.settings,
    queryFn: fetchAdminSettingsStatus,
    staleTime: 60_000,
  })

  const data = settingsQ.data

  return (
    <div className="space-y-4">
      <PageHeader
        title="Admin settings"
        description="Read-only integration status from server environment. Credentials are never exposed in the dashboard; set variables in deployment configuration."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void settingsQ.refetch()}>
              Refresh status
            </Button>
            <Button variant="outline" asChild>
              <Link to="/admin">Back to admin home</Link>
            </Button>
          </>
        }
      />

      <div className="rounded-lg border border-border bg-card p-4 text-sm">
        <p>
          <span className="text-muted-foreground">Environment:</span>{' '}
          <span className="font-medium">{data?.environment ?? '—'}</span>
        </p>
        <p className="mt-1">
          <span className="text-muted-foreground">Debug mode:</span>{' '}
          <span className="font-medium">{data?.debug ? 'On' : 'Off'}</span>
        </p>
      </div>

      <div className="space-y-3">
        <h3 className="font-semibold text-foreground">Integrations</h3>
        {settingsQ.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading status…</p>
        ) : (
          (data?.integrations ?? []).map((row) => (
            <div key={row.id} className="rounded-lg border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-foreground">{row.label}</p>
                {statusBadge(row.status, row.configured)}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Feature {row.enabled ? 'enabled' : 'disabled'} ·{' '}
                {row.configured ? 'credentials present' : 'credentials missing'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{row.hint}</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
