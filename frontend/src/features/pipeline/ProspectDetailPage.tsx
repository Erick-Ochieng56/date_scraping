import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ProspectReviewCard } from '@/features/pipeline/ProspectReviewCard'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getProspect, prospectConvert, prospectMarkContacted, prospectReject } from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'

export function ProspectDetailPage() {
  const params = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const prospectId = Number(params.prospectId)

  const q = useQuery({
    queryKey: ['prospect', prospectId],
    queryFn: () => getProspect(prospectId),
    enabled: prospectId > 0,
  })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['prospects'] })
    void qc.invalidateQueries({ queryKey: ['leads'] })
    void qc.invalidateQueries({ queryKey: ['prospect', prospectId] })
  }
  const contactedM = useMutation({ mutationFn: () => prospectMarkContacted(prospectId), onSuccess: refresh })
  const convertM = useMutation({
    mutationFn: () => prospectConvert(prospectId),
    onSuccess: (data) => {
      refresh()
      if (data.lead_id) navigate(`/leads/${data.lead_id}`)
    },
  })
  const rejectM = useMutation({ mutationFn: () => prospectReject(prospectId), onSuccess: refresh })

  const prospect = q.data

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link className="text-sm text-primary hover:underline" to="/prospects">
        ← Back to review queue
      </Link>
      {prospect ? (
        <ProspectReviewCard
          prospect={prospect}
          onReject={() => rejectM.mutate()}
          onContacted={() => contactedM.mutate()}
          onConvert={() => convertM.mutate()}
          rejectPending={rejectM.isPending}
          contactedPending={contactedM.isPending}
          convertPending={convertM.isPending}
        />
      ) : q.isError ? (
        <AlertBanner error={getApiErrorMessage(q.error, 'Failed to load this prospect.')} />
      ) : (
        <p className="text-sm text-muted-foreground">Loading prospect…</p>
      )}
    </div>
  )
}
