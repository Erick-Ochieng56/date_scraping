import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { classifyProspectSource, SOURCE_META } from '@/features/pipeline/evidence'
import { cn } from '@/lib/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getLead, leadMarkInterested, leadReject, leadSyncCrm } from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'

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

  const lead = q.data
  const sourceMeta = lead ? SOURCE_META[classifyProspectSource(lead.source_name)] : null

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link className="text-sm text-primary hover:underline" to="/leads">
        ← Back to my leads
      </Link>

      {lead ? (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {sourceMeta ? (
              <span
                className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold', sourceMeta.softClass, sourceMeta.textClass)}
              >
                Found by {sourceMeta.label}
              </span>
            ) : null}
            {lead.prospect_id ? (
              <Link className="text-xs text-muted-foreground hover:text-primary hover:underline" to={`/prospects/${lead.prospect_id}`}>
                View original prospect →
              </Link>
            ) : null}
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-foreground">{lead.full_name || lead.company || `Lead #${leadId}`}</h2>
          {lead.full_name && lead.company ? <p className="mt-1 text-muted-foreground">{lead.company}</p> : null}
          {lead.event_name ? <p className="mt-1 text-sm text-muted-foreground">{lead.event_name}</p> : null}

          <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
            {lead.email ? (
              <span>
                Email — <span className="text-foreground">{lead.email}</span>
              </span>
            ) : null}
            {lead.phone_raw ? (
              <span>
                Phone — <span className="text-foreground">{lead.phone_raw}</span>
              </span>
            ) : null}
            {lead.website ? (
              <a className="text-primary hover:underline" href={lead.website} target="_blank" rel="noreferrer">
                Visit website
              </a>
            ) : null}
            <span>
              Status — <span className="text-foreground">{lead.status}</span>
            </span>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            <Button disabled={lead.status !== 'contacted' || interestedM.isPending} onClick={() => interestedM.mutate()}>
              Mark interested
            </Button>
            <Button variant="outline" disabled={lead.status !== 'interested' || syncM.isPending} onClick={() => syncM.mutate()}>
              Sync to CRM
            </Button>
            <Button
              variant="destructive"
              disabled={['rejected', 'synced'].includes(lead.status) || rejectM.isPending}
              onClick={() => rejectM.mutate()}
            >
              Not relevant
            </Button>
          </div>
        </div>
      ) : q.isError ? (
        <AlertBanner error={getApiErrorMessage(q.error, 'Failed to load this lead.')} />
      ) : (
        <p className="text-sm text-muted-foreground">Loading lead…</p>
      )}
    </div>
  )
}
