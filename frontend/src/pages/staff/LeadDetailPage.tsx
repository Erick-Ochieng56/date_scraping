import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getLead, leadMarkInterested, leadReject, leadSyncCrm } from '@/lib/api/dashboard'

export function LeadDetailPage() {
  const params = useParams()
  const qc = useQueryClient()
  const leadId = Number(params.leadId)

  const q = useQuery({
    queryKey: ['lead', leadId],
    queryFn: () => getLead(leadId),
    enabled: leadId > 0,
  })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['leads'] })
    void qc.invalidateQueries({ queryKey: ['lead', leadId] })
  }
  const interestedM = useMutation({ mutationFn: () => leadMarkInterested(leadId), onSuccess: refresh })
  const rejectM = useMutation({ mutationFn: () => leadReject(leadId), onSuccess: refresh })
  const syncM = useMutation({ mutationFn: () => leadSyncCrm(leadId), onSuccess: refresh })

  const l = q.data

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-foreground">Lead #{leadId}</h2>
        <Link className="text-sm text-primary hover:underline" to="/leads">
          Back to my leads
        </Link>
      </div>
      {l ? (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Name</p>
              <p className="font-medium">{l.full_name || '-'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Company</p>
              <p className="font-medium">{l.company || '-'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Status</p>
              <p className="font-medium">{l.status}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Email</p>
              <p className="font-medium">{l.email || '-'}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={l.status !== 'contacted' || interestedM.isPending} onClick={() => interestedM.mutate()}>
              Mark interested
            </Button>
            <Button disabled={l.status !== 'interested' || syncM.isPending} onClick={() => syncM.mutate()}>
              Sync to CRM
            </Button>
            <Button variant="destructive" disabled={['rejected', 'synced'].includes(l.status) || rejectM.isPending} onClick={() => rejectM.mutate()}>
              Not relevant
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Loading lead...</p>
      )}
    </div>
  )
}

