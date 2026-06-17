import { useCallback, useMemo, useState } from 'react'

export function useRowSelection<TId extends number | string>(getId: (row: { id: TId }) => TId) {
  const [selected, setSelected] = useState<TId[]>([])

  const toggle = useCallback(
    (id: TId, checked: boolean) => {
      setSelected((prev) => (checked ? [...prev, id] : prev.filter((x) => x !== id)))
    },
    []
  )

  const toggleAll = useCallback(
    (rows: Array<{ id: TId }>, checked: boolean) => {
      setSelected(checked ? rows.map(getId) : [])
    },
    [getId]
  )

  const clear = useCallback(() => setSelected([]), [])

  const isAllSelected = useCallback(
    (rows: Array<{ id: TId }>) => rows.length > 0 && rows.every((r) => selected.includes(getId(r))),
    [getId, selected]
  )

  const canBulk = selected.length > 0

  return useMemo(
    () => ({
      selected,
      setSelected,
      toggle,
      toggleAll,
      clear,
      isAllSelected,
      canBulk,
    }),
    [selected, toggle, toggleAll, clear, isAllSelected, canBulk]
  )
}
