import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { listLeads, listProspects } from '@/lib/api/dashboard'

export function AdminPipelinePage() {
  const prospectsQ = useQuery({ queryKey: ['admin-pipeline-prospects'], queryFn: () => listProspects({ page_size: 1 }) })
  const leadsQ = useQuery({ queryKey: ['admin-pipeline-leads'], queryFn: () => listLeads({ page_size: 1 }) })

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Pipeline oversight</h2>
        <p className="mt-1 text-sm text-muted-foreground">Cross-user prospects and leads governance for admin operations.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Prospects</p>
          <p className="text-2xl font-semibold">{prospectsQ.data?.total ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Leads</p>
          <p className="text-2xl font-semibold">{leadsQ.data?.total ?? 0}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" asChild>
          <Link to="/prospects">Open prospects</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/leads">Open leads</Link>
        </Button>
      </div>
    </div>
  )
}
