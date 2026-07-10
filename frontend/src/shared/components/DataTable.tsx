import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from '@tanstack/react-table'
import { useMemo } from 'react'

import { cn } from '@/lib/utils'

type DataTableSurface = 'standalone' | 'embedded'

type DataTableProps<T> = {
  columns: ColumnDef<T, unknown>[]
  data: T[]
  isLoading?: boolean
  emptyMessage?: string
  getRowId?: (row: T) => string
  rowSelection?: RowSelectionState
  onRowSelectionChange?: (state: RowSelectionState) => void
  enableRowSelection?: boolean
  surface?: DataTableSurface
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  emptyMessage = 'No records found.',
  getRowId,
  rowSelection,
  onRowSelectionChange,
  enableRowSelection = false,
  surface = 'standalone',
  className,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: getRowId ? (row) => getRowId(row) : undefined,
    enableRowSelection,
    state: rowSelection !== undefined ? { rowSelection } : undefined,
    onRowSelectionChange: onRowSelectionChange
      ? (updater) => {
          const next = typeof updater === 'function' ? updater(rowSelection ?? {}) : updater
          onRowSelectionChange(next)
        }
      : undefined,
  })

  const colCount = useMemo(() => table.getAllColumns().length, [table])
  const embedded = surface === 'embedded'

  return (
    <div
      className={cn(
        'overflow-auto',
        !embedded && 'rounded-xl border border-border bg-card',
        className
      )}
    >
      <table className="min-w-full text-sm">
        <thead className="border-b border-border/80 bg-muted/30">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="bg-card">
          {isLoading && data.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-10 text-center text-muted-foreground">
                Loading…
              </td>
            </tr>
          ) : null}
          {!isLoading && data.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-4 py-10 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          ) : null}
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="border-b border-border/50 align-top transition-colors last:border-b-0 hover:bg-muted/15"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-3 text-foreground">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
