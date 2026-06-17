import { Button } from '@/components/ui/button'

type ListPaginationProps = {
  page: number
  pageSize: number
  total: number
  hasNext: boolean
  onPrev: () => void
  onNext: () => void
  isLoading?: boolean
}

export function ListPagination({ page, pageSize, total, hasNext, onPrev, onNext, isLoading }: ListPaginationProps) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
      <p>
        {total === 0 ? 'No results' : `Showing ${start}–${end} of ${total}`}
        {isLoading ? ' · Loading…' : null}
      </p>
      <div className="flex gap-2">
        <Button type="button" variant="outline" size="sm" disabled={page <= 1 || isLoading} onClick={onPrev}>
          Previous
        </Button>
        <Button type="button" variant="outline" size="sm" disabled={!hasNext || isLoading} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  )
}
