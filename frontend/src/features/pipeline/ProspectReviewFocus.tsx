import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ProspectReviewCard } from '@/features/pipeline/ProspectReviewCard'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getProspect, listProspects, prospectConvert, prospectMarkContacted, prospectReject } from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'

type Decision = 'rejected' | 'contacted' | 'lead'

const DECISION_LABEL: Record<Decision, string> = {
  rejected: 'Marked not relevant',
  contacted: 'Marked as contacted',
  lead: 'Tracking as a lead',
}

const UNDO_WINDOW_MS = 4000

export function ProspectReviewFocus({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [decided, setDecided] = useState<Record<number, Decision>>({})
  const [index, setIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)
  // The undo-window commit is timer-driven, so its state must live in a ref, not
  // useState — a setTimeout callback closes over whatever `pending` was in the
  // render it was scheduled from, which is always one decision behind by the
  // time the timer fires. `pendingDisplay` mirrors the ref just for the toast UI.
  const pending = useRef<{ id: number; action: Decision } | null>(null)
  const pendingTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [pendingDisplay, setPendingDisplay] = useState<{ id: number; action: Decision } | null>(null)

  const queueQ = useQuery({
    // Deliberately NOT prefixed with 'prospects' — the list/detail mutations
    // invalidate that key on every decision to refresh the page behind this
    // overlay, which would also refetch (and shrink) this snapshot mid-session
    // and corrupt the progress counter.
    queryKey: ['review-focus-queue'],
    queryFn: () => listProspects({ status: 'new', page_size: 100 }),
    enabled: open,
    staleTime: Infinity,
  })

  const total = queueQ.data?.items.length ?? 0
  const remaining = useMemo(
    () => (queueQ.data?.items ?? []).filter((p) => !decided[p.id]),
    [queueQ.data, decided]
  )
  const doneCount = total - remaining.length

  useEffect(() => {
    if (open) {
      setDecided({})
      setIndex(0)
      setError(null)
    }
  }, [open])

  const currentIndex = Math.min(index, Math.max(0, remaining.length - 1))
  const current = remaining[currentIndex]

  const detailQ = useQuery({
    queryKey: ['prospect', current?.id],
    queryFn: () => getProspect(current!.id),
    enabled: open && current != null,
  })

  const runMutation = async (id: number, action: Decision) => {
    try {
      if (action === 'rejected') await prospectReject(id)
      else if (action === 'contacted') await prospectMarkContacted(id)
      else await prospectConvert(id)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not save that decision. It has been put back in your queue.'))
      setDecided((d) => {
        const next = { ...d }
        delete next[id]
        return next
      })
    } finally {
      void qc.invalidateQueries({ queryKey: ['prospects'] })
      void qc.invalidateQueries({ queryKey: ['leads'] })
      void qc.invalidateQueries({ queryKey: ['metrics-summary'] })
    }
  }

  const commitPending = () => {
    if (pendingTimer.current) clearTimeout(pendingTimer.current)
    pendingTimer.current = null
    const p = pending.current
    pending.current = null
    setPendingDisplay(null)
    if (p) void runMutation(p.id, p.action)
  }

  // Flush any pending (undo-window) decision if the overlay closes before the timer fires.
  useEffect(() => {
    if (!open && pending.current) commitPending()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => () => {
    if (pendingTimer.current) clearTimeout(pendingTimer.current)
  }, [])

  const decide = (id: number, action: Decision) => {
    commitPending()
    setError(null)
    setDecided((d) => ({ ...d, [id]: action }))
    pending.current = { id, action }
    setPendingDisplay({ id, action })
    pendingTimer.current = setTimeout(commitPending, UNDO_WINDOW_MS)
  }

  const undo = () => {
    const p = pending.current
    if (!p) return
    if (pendingTimer.current) clearTimeout(pendingTimer.current)
    pendingTimer.current = null
    pending.current = null
    setDecided((d) => {
      const next = { ...d }
      delete next[p.id]
      return next
    })
    setPendingDisplay(null)
  }

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (!current) return
      if (e.key === '1') decide(current.id, 'rejected')
      if (e.key === '2') decide(current.id, 'contacted')
      if (e.key === '3') decide(current.id, 'lead')
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, current])

  if (!open) return null

  const byAction = (action: Decision) => Object.values(decided).filter((a) => a === action).length
  const isDone = total > 0 && remaining.length === 0

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Review prospects one by one"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-foreground/40 px-4 py-8 backdrop-blur-sm sm:py-14"
    >
      <div className="w-full max-w-2xl">
        <div className="mb-4 flex items-center gap-4 text-primary-foreground">
          <span className="text-sm font-medium tabular-nums">
            {isDone ? 'Done' : `${Math.min(doneCount + 1, total)} of ${total}`}
          </span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/25">
            <div
              className="h-full rounded-full bg-white transition-[width] duration-300"
              style={{ width: `${total > 0 ? (doneCount / total) * 100 : 0}%` }}
            />
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded-md bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25"
          >
            <X className="size-3.5" aria-hidden />
            Close
          </button>
        </div>

        {error ? <AlertBanner error={error} className="mb-4" /> : null}

        {queueQ.isLoading ? (
          <div className="rounded-2xl bg-card p-10 text-center text-sm text-muted-foreground shadow-lg">
            Loading your review queue…
          </div>
        ) : total === 0 ? (
          <div className="rounded-2xl bg-card p-10 text-center shadow-lg">
            <p className="text-lg font-semibold text-foreground">Nothing to review</p>
            <p className="mt-1 text-sm text-muted-foreground">There are no new prospects waiting right now.</p>
            <Button className="mt-5" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : isDone ? (
          <div className="review-card-enter rounded-2xl bg-card p-10 text-center shadow-lg">
            <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-chart-2/10 text-chart-2">
              <CheckCircle2 className="size-7" aria-hidden />
            </div>
            <p className="mt-4 text-lg font-semibold text-foreground">All caught up</p>
            <p className="mt-1 text-sm text-muted-foreground">
              You reviewed {total} prospect{total === 1 ? '' : 's'}.
            </p>
            <div className="mt-6 flex justify-center gap-8">
              <div>
                <p className="text-2xl font-semibold tabular-nums text-chart-2">{byAction('lead')}</p>
                <p className="text-xs text-muted-foreground">Tracked as leads</p>
              </div>
              <div>
                <p className="text-2xl font-semibold tabular-nums text-primary">{byAction('contacted')}</p>
                <p className="text-xs text-muted-foreground">Contacted</p>
              </div>
              <div>
                <p className="text-2xl font-semibold tabular-nums text-muted-foreground">{byAction('rejected')}</p>
                <p className="text-xs text-muted-foreground">Not relevant</p>
              </div>
            </div>
            <Button className="mt-6" onClick={onClose}>
              Back to queue
            </Button>
          </div>
        ) : current && detailQ.data ? (
          <div key={current.id} className="review-card-enter">
            <ProspectReviewCard
              prospect={detailQ.data}
              onReject={() => decide(current.id, 'rejected')}
              onContacted={() => decide(current.id, 'contacted')}
              onConvert={() => decide(current.id, 'lead')}
            />
            <p className="mt-3 text-center text-xs text-white/70">
              Shortcuts: <kbd className="rounded bg-white/15 px-1.5 py-0.5">1</kbd> not relevant ·{' '}
              <kbd className="rounded bg-white/15 px-1.5 py-0.5">2</kbd> contacted ·{' '}
              <kbd className="rounded bg-white/15 px-1.5 py-0.5">3</kbd> track as lead
            </p>
          </div>
        ) : (
          <div className="rounded-2xl bg-card p-10 text-center text-sm text-muted-foreground shadow-lg">Loading…</div>
        )}
      </div>

      {pendingDisplay ? (
        <div className="fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-4 rounded-lg bg-foreground px-4 py-2.5 text-sm text-background shadow-lg">
          <span>{DECISION_LABEL[pendingDisplay.action]}</span>
          <button type="button" onClick={undo} className="font-semibold underline underline-offset-2">
            Undo
          </button>
        </div>
      ) : null}
    </div>
  )
}
