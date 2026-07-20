import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from '@tanstack/react-table'
import { useMemo } from 'react'

import { cn } from '@/lib/utils'

type DataTableProps<T> = {
  columns: ColumnDef<T, unknown>[]
  data: T[]
  isLoading?: boolean
  /**
   * Set when the query that feeds `data` failed. Without this, a failed fetch
   * used to render the emptyMessage ("No records found.") — visually
   * indistinguishable from a legitimately empty result, hiding real backend/
   * network errors from the user on every list in the app.
   */
  errorMessage?: string | null
  emptyMessage?: string
  getRowId?: (row: T) => string
  rowSelection?: RowSelectionState
  onRowSelectionChange?: (state: RowSelectionState) => void
  enableRowSelection?: boolean
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  errorMessage = null,
  emptyMessage = 'No records found.',
  getRowId,
  rowSelection,
  onRowSelectionChange,
  enableRowSelection = false,
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

  return (
    <div className={cn('overflow-auto rounded-lg border border-border', className)}>
      <table className="min-w-full text-sm">
        <thead className="bg-muted">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th key={header.id} className="px-3 py-2 text-left font-medium text-foreground">
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {errorMessage && data.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-destructive" role="alert">
                {errorMessage}
              </td>
            </tr>
          ) : null}
          {!errorMessage && isLoading && data.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-muted-foreground">
                Loading…
              </td>
            </tr>
          ) : null}
          {!errorMessage && !isLoading && data.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          ) : null}
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-t border-border align-top">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
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
