import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  prospectConvert,
  prospectMarkContacted,
  prospectReject,
  listProspects,
  prospectsBulkContacted,
  prospectsBulkConvert,
  prospectsBulkReject,
} from '@/lib/api/dashboard'

export function ProspectsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<number[]>([])

  const prospectsQ = useQuery({
    queryKey: ['prospects', status, search],
    queryFn: () => listProspects({ status: status || undefined, search: search || undefined, page_size: 50 }),
  })

  const refresh = () => {
    setSelected([])
    void qc.invalidateQueries({ queryKey: ['prospects'] })
    void qc.invalidateQueries({ queryKey: ['leads'] })
  }

  const contactM = useMutation({ mutationFn: () => prospectsBulkContacted(selected), onSuccess: refresh })
  const convertM = useMutation({ mutationFn: () => prospectsBulkConvert(selected), onSuccess: refresh })
  const rejectM = useMutation({ mutationFn: () => prospectsBulkReject(selected), onSuccess: refresh })
  const rowContactM = useMutation({ mutationFn: (id: number) => prospectMarkContacted(id), onSuccess: refresh })
  const rowConvertM = useMutation({ mutationFn: (id: number) => prospectConvert(id), onSuccess: refresh })
  const rowRejectM = useMutation({ mutationFn: (id: number) => prospectReject(id), onSuccess: refresh })

  const canBulk = selected.length > 0
  const rows = prospectsQ.data?.items ?? []

  const allSelected = rows.length > 0 && rows.every((row) => selected.includes(row.id))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold text-foreground">Prospects</h2>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canBulk || contactM.isPending} onClick={() => contactM.mutate()}>
            Mark contacted
          </Button>
          <Button disabled={!canBulk || convertM.isPending} onClick={() => convertM.mutate()}>
            Convert to leads
          </Button>
          <Button variant="outline" disabled={!canBulk || rejectM.isPending} onClick={() => rejectM.mutate()}>
            Reject
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="Search company, event, email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="converted">Converted</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <p className="text-sm text-muted-foreground">
        Select records then use actions above. This is designed for non-technical daily lead workflow.
      </p>
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
              <th className="px-3 py-2 text-left">Company</th>
              <th className="px-3 py-2 text-left">Event</th>
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
                <td className="px-3 py-2">{row.company || '-'}</td>
                <td className="px-3 py-2">{row.event_name || '-'}</td>
                <td className="px-3 py-2">{row.email || '-'}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/prospects/${row.id}`}>View</Link>
                    </Button>
                    <Button
                      size="sm"
                      disabled={row.status !== 'new' || rowContactM.isPending}
                      onClick={() => rowContactM.mutate(row.id)}
                    >
                      Contacted
                    </Button>
                    <Button
                      size="sm"
                      disabled={!['new', 'contacted'].includes(row.status) || rowConvertM.isPending}
                      onClick={() => rowConvertM.mutate(row.id)}
                    >
                      Convert
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={row.status === 'rejected' || rowRejectM.isPending}
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
      {prospectsQ.isLoading ? <p>Loading prospects...</p> : null}
    </div>
  )
}

