import { Link } from 'react-router-dom'

import type { DuplicateMatch } from '@/shared/api/types'
import { duplicateMatchLabel } from '@/features/pipeline/leadUtils'

type DuplicateMatchesPanelProps = {
  items: DuplicateMatch[]
  basePath: '/prospects' | '/leads'
  loading?: boolean
}

export function DuplicateMatchesPanel({ items, basePath, loading }: DuplicateMatchesPanelProps) {
  if (loading) {
    return <p className="text-sm text-muted-foreground">Checking for duplicates…</p>
  }
  if (items.length === 0) {
    return null
  }

  return (
    <div className="rounded-lg border border-amber-300/60 bg-amber-50/50 p-4 dark:border-amber-700/50 dark:bg-amber-950/20">
      <h3 className="font-semibold text-amber-900 dark:text-amber-200">Possible duplicates ({items.length})</h3>
      <ul className="mt-2 space-y-2 text-sm">
        {items.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-card px-3 py-2">
            <div>
              <p className="font-medium">{row.company || row.full_name || `Record #${row.id}`}</p>
              <p className="text-xs text-muted-foreground">
                {duplicateMatchLabel(row.match_reason)} · {row.status}
                {row.email ? ` · ${row.email}` : ''}
              </p>
            </div>
            <Link className="font-medium text-info hover:underline" to={`${basePath}/${row.id}`}>
              Open
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
