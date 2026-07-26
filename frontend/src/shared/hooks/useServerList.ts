import { useQuery, type Query } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'

import type { Paginated } from '@/shared/api/types'
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue'

type UseServerListOptions<T, F extends Record<string, unknown>, R extends Paginated<T>> = {
  queryKey: readonly unknown[]
  queryFn: (params: F & { page: number; page_size: number }) => Promise<R>
  pageSize?: number
  filters?: F
  search?: string
  searchDebounceMs?: number
  enabled?: boolean
  refetchInterval?: number | false | ((query: Query<R, Error>) => number | false)
}

export function useServerList<T, F extends Record<string, unknown> = Record<string, never>, R extends Paginated<T> = Paginated<T>>({
  queryKey,
  queryFn,
  pageSize = 25,
  filters,
  search = '',
  searchDebounceMs = 300,
  enabled = true,
  refetchInterval,
}: UseServerListOptions<T, F, R>) {
  const [page, setPage] = useState(1)
  const debouncedSearch = useDebouncedValue(search, searchDebounceMs)

  const stableFilters = useMemo(() => filters ?? ({} as F), [filters])

  const listQ = useQuery({
    queryKey: [...queryKey, page, pageSize, debouncedSearch, stableFilters],
    queryFn: () =>
      queryFn({
        ...stableFilters,
        page,
        page_size: pageSize,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
      } as F & { page: number; page_size: number; search?: string }),
    enabled,
    refetchInterval,
  })

  const resetPage = useCallback(() => setPage(1), [])

  const goNext = useCallback(() => {
    if (listQ.data?.has_next) setPage((p) => p + 1)
  }, [listQ.data?.has_next])

  const goPrev = useCallback(() => {
    setPage((p) => Math.max(1, p - 1))
  }, [])

  return {
    query: listQ,
    items: listQ.data?.items ?? [],
    total: listQ.data?.total ?? 0,
    page,
    pageSize,
    hasNext: listQ.data?.has_next ?? false,
    setPage,
    goNext,
    goPrev,
    resetPage,
    debouncedSearch,
  }
}
