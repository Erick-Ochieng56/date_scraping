import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  leadMarkInterested,
  leadReject,
  leadSyncCrm,
  leadsBulkInterested,
  leadsBulkReject,
  listLeads,
} from '@/lib/api/dashboard'

export function LeadsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<number[]>([])

  const leadsQ = useQuery({
    queryKey: ['leads', status, search],
    queryFn: () => listLeads({ status: status || undefined, search: search || undefined, page_size: 50 }),
  })

  const refresh = () => {
    setSelected([])
    void qc.invalidateQueries({ queryKey: ['leads'] })
  }

  const interestedM = useMutation({ mutationFn: () => leadsBulkInterested(selected), onSuccess: refresh })
  const rejectM = useMutation({ mutationFn: () => leadsBulkReject(selected), onSuccess: refresh })
  const rowInterestedM = useMutation({ mutationFn: (id: number) => leadMarkInterested(id), onSuccess: refresh })
  const rowRejectM = useMutation({ mutationFn: (id: number) => leadReject(id), onSuccess: refresh })
  const rowSyncM = useMutation({ mutationFn: (id: number) => leadSyncCrm(id), onSuccess: refresh })

  const canBulk = selected.length > 0
  const rows = leadsQ.data?.items ?? []
  const allSelected = rows.length > 0 && rows.every((row) => selected.includes(row.id))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold text-foreground">Leads</h2>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canBulk || interestedM.isPending} onClick={() => interestedM.mutate()}>
            Mark interested
          </Button>
          <Button variant="outline" disabled={!canBulk || rejectM.isPending} onClick={() => rejectM.mutate()}>
            Reject
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="Search company, name, email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="contacted">Contacted</option>
          <option value="interested">Interested</option>
          <option value="rejected">Rejected</option>
          <option value="synced">Synced</option>
        </select>
      </div>
      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) =>
                    setSelected(e.target.checked ? rows.map((row) => row.id) : [])
                  }
                />
              </th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Company</th>
              <th className="px-3 py-2 text-left">Email</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(row.id)}
                    onChange={(e) =>
                      setSelected((prev) =>
                        e.target.checked ? [...prev, row.id] : prev.filter((id) => id !== row.id)
                      )
                    }
                  />
                </td>
                <td className="px-3 py-2">{row.full_name || '-'}</td>
                <td className="px-3 py-2">{row.company || '-'}</td>
                <td className="px-3 py-2">{row.email || '-'}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/leads/${row.id}`}>View</Link>
                    </Button>
                    <Button
                      size="sm"
                      disabled={row.status !== 'contacted' || rowInterestedM.isPending}
                      onClick={() => rowInterestedM.mutate(row.id)}
                    >
                      Interested
                    </Button>
                    <Button
                      size="sm"
                      disabled={row.status !== 'interested' || rowSyncM.isPending}
                      onClick={() => rowSyncM.mutate(row.id)}
                    >
                      Sync CRM
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={['rejected', 'synced'].includes(row.status) || rowRejectM.isPending}
                      onClick={() => rowRejectM.mutate(row.id)}
                    >
                      Reject
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {leadsQ.isLoading ? <p>Loading leads...</p> : null}
    </div>
  )
}

