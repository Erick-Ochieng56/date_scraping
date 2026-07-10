import { type ColumnDef } from '@tanstack/react-table'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ScoreBadge } from '@/shared/components/ScoreBadge'
import { StatusBadge } from '@/shared/components/StatusBadge'
import type { Prospect } from '@/shared/api/types'

export type ProspectRowActions = {
  onContact: (id: number) => void
  onConvert: (id: number) => void
  onReject: (id: number) => void
  contactPending?: boolean
  convertPending?: boolean
  rejectPending?: boolean
}

export function prospectBaseColumns(): ColumnDef<Prospect, unknown>[] {
  return [
    {
      accessorKey: 'translation_need_score',
      header: 'Score',
      cell: ({ row }) => (
        <ScoreBadge score={row.original.translation_need_score} label={row.original.score_label} />
      ),
    },
    {
      accessorKey: 'source_name',
      header: 'Source',
      cell: ({ row }) => row.original.source_name || '—',
    },
    {
      accessorKey: 'company',
      header: 'Company',
      cell: ({ row }) => row.original.company || '—',
    },
    {
      accessorKey: 'event_name',
      header: 'Event',
      cell: ({ row }) => row.original.event_name || '—',
    },
    {
      accessorKey: 'email',
      header: 'Email',
      cell: ({ row }) => row.original.email || '—',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => <StatusBadge status={row.original.status} kind="prospect" />,
    },
  ]
}

export function prospectActionColumns(actions: ProspectRowActions): ColumnDef<Prospect, unknown>[] {
  return [
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const p = row.original
        return (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to={`/prospects/${p.id}`}>View</Link>
            </Button>
            <Button
              size="sm"
              disabled={p.status !== 'new' || actions.contactPending}
              onClick={() => actions.onContact(p.id)}
            >
              Contacted
            </Button>
            <Button
              size="sm"
              disabled={!['new', 'contacted'].includes(p.status) || actions.convertPending}
              onClick={() => actions.onConvert(p.id)}
            >
              Convert
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={p.status === 'rejected' || actions.rejectPending}
              onClick={() => actions.onReject(p.id)}
            >
              Reject
            </Button>
          </div>
        )
      },
    },
  ]
}
