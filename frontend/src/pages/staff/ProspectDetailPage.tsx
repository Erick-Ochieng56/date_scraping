import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getProspect, prospectConvert, prospectMarkContacted, prospectReject } from '@/lib/api/dashboard'

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

  const p = q.data

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-foreground">Prospect #{prospectId}</h2>
        <Link className="text-sm text-primary hover:underline" to="/prospects">
          Back to prospects
        </Link>
      </div>
      {p ? (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Company</p>
              <p className="font-medium">{p.company || '-'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Status</p>
              <p className="font-medium">{p.status}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Event</p>
              <p className="font-medium">{p.event_name || '-'}</p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground">Email</p>
              <p className="font-medium">{p.email || '-'}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={p.status !== 'new' || contactedM.isPending} onClick={() => contactedM.mutate()}>
              Mark contacted
            </Button>
            <Button disabled={!['new', 'contacted'].includes(p.status) || convertM.isPending} onClick={() => convertM.mutate()}>
              Convert to lead
            </Button>
            <Button variant="outline" disabled={p.status === 'rejected' || rejectM.isPending} onClick={() => rejectM.mutate()}>
              Reject
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Loading prospect...</p>
      )}
    </div>
  )
}

