import { ExternalLink, Star } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { getProspectEvidence, SOURCE_META, type MatchLabel } from '@/features/pipeline/evidence'
import { cn } from '@/lib/utils'
import type { ProspectDetail } from '@/shared/api/types'

const MATCH_CHIP_CLASS: Record<MatchLabel, string> = {
  'Strong match': 'bg-chart-2/10 text-chart-2',
  'Possible match': 'text-amber-700 bg-amber-500/10 dark:text-amber-400',
  'Weak match': 'bg-muted text-muted-foreground',
}

function Chip({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold', className)}>
      {children}
    </span>
  )
}

function formatEventDate(iso: string | null) {
  if (!iso) return null
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatAddedDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export type ProspectReviewCardProps = {
  prospect: ProspectDetail
  onReject: () => void
  onContacted: () => void
  onConvert: () => void
  rejectPending?: boolean
  contactedPending?: boolean
  convertPending?: boolean
}

export function ProspectReviewCard({
  prospect,
  onReject,
  onContacted,
  onConvert,
  rejectPending,
  contactedPending,
  convertPending,
}: ProspectReviewCardProps) {
  const evidence = getProspectEvidence(prospect)
  const sourceMeta = SOURCE_META[evidence.source]
  const eventDateLabel = formatEventDate(prospect.event_date)

  const heading = prospect.company || prospect.event_name || `Prospect #${prospect.id}`
  const subtitle = prospect.company && prospect.event_name ? prospect.event_name : null

  const canContact = prospect.status === 'new'
  const canConvert = prospect.status === 'new' || prospect.status === 'contacted'
  const canReject = prospect.status !== 'rejected'

  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
      <div className="mb-4 flex flex-wrap gap-2">
        <Chip className={cn(sourceMeta.softClass, sourceMeta.textClass)}>Found by {evidence.sourceLabel}</Chip>
        {evidence.matchLabel ? <Chip className={MATCH_CHIP_CLASS[evidence.matchLabel]}>{evidence.matchLabel}</Chip> : null}
        {eventDateLabel ? <Chip className="bg-primary/10 text-primary tabular-nums">{eventDateLabel}</Chip> : null}
      </div>

      <h2 className="text-2xl font-semibold tracking-tight text-foreground">{heading}</h2>
      {subtitle ? <p className="mt-1 text-muted-foreground">{subtitle}</p> : null}

      {evidence.evidenceText ? (
        <div className="mt-5 rounded-lg border-l-4 border-primary bg-primary/5 px-4 py-3 text-sm">
          <p className="text-foreground">&ldquo;{evidence.evidenceText}&rdquo;</p>
          {evidence.signals.length > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">Signals: {evidence.signals.join(', ')}</p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
        {prospect.email ? (
          <span>
            Email — <span className="text-foreground">{prospect.email}</span>
          </span>
        ) : null}
        {prospect.phone_raw ? (
          <span>
            Phone — <span className="text-foreground">{prospect.phone_raw}</span>
          </span>
        ) : null}
        {prospect.website || prospect.source_url ? (
          <a
            className="inline-flex items-center gap-1 text-primary hover:underline"
            href={prospect.website || prospect.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Visit website
            <ExternalLink className="size-3.5" aria-hidden />
          </a>
        ) : null}
        <span>
          Added — <span className="text-foreground">{formatAddedDate(prospect.created_at)}</span>
        </span>
      </div>

      <div className="mt-6 grid gap-2 sm:grid-cols-[1fr_1fr_1.4fr]">
        <Button
          variant="destructive"
          disabled={!canReject || rejectPending}
          onClick={onReject}
          className="justify-center"
        >
          Not relevant
        </Button>
        <Button
          variant="outline"
          disabled={!canContact || contactedPending}
          onClick={onContacted}
          className="justify-center"
        >
          Contacted
        </Button>
        <Button disabled={!canConvert || convertPending} onClick={onConvert} className="justify-center">
          <Star className="mr-1.5 size-4" aria-hidden />
          Track as lead
        </Button>
      </div>
    </div>
  )
}
