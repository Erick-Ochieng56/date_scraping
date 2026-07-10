import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  getProspect,
  getProspectDuplicates,
  prospectConvert,
  prospectEnrich,
  prospectMarkContacted,
  prospectReject,
  updateProspect,
} from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DetailField } from '@/shared/components/DetailField'
import { ExternalTextLink } from '@/shared/components/TextLink'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { ScoreBadge } from '@/shared/components/ScoreBadge'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { DuplicateMatchesPanel } from '@/features/pipeline/DuplicateMatchesPanel'

export function ProspectDetailPage() {
  const params = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const prospectId = Number(params.prospectId)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ company: '', event_name: '', email: '', phone_raw: '', website: '', notes: '' })

  const q = useQuery({
    queryKey: ['prospect', prospectId],
    queryFn: () => getProspect(prospectId),
    enabled: prospectId > 0,
  })

  const duplicatesQ = useQuery({
    queryKey: ['prospect-duplicates', prospectId],
    queryFn: () => getProspectDuplicates(prospectId),
    enabled: prospectId > 0,
  })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['prospects'] })
    void qc.invalidateQueries({ queryKey: ['leads'] })
    void qc.invalidateQueries({ queryKey: ['prospect', prospectId] })
  }

  const onError = (err: unknown) => setBanner({ error: getApiErrorMessage(err) })

  const contactedM = useMutation({
    mutationFn: () => prospectMarkContacted(prospectId),
    onSuccess: () => {
      setBanner({ message: 'Marked as contacted.' })
      refresh()
    },
    onError,
  })
  const convertM = useMutation({
    mutationFn: () => prospectConvert(prospectId),
    onSuccess: (data) => {
      refresh()
      if (data.lead_id) navigate(`/leads/${data.lead_id}`)
    },
    onError,
  })
  const rejectM = useMutation({
    mutationFn: () => prospectReject(prospectId),
    onSuccess: () => {
      setBanner({ message: 'Prospect rejected.' })
      refresh()
    },
    onError,
  })
  const enrichM = useMutation({
    mutationFn: () => prospectEnrich(prospectId, { force: true }),
    onSuccess: (res) => {
      if (res.skipped) {
        setBanner({ message: 'Enrichment skipped — contact fields already populated.' })
      } else if (res.updated_fields?.length) {
        setBanner({ message: `Enriched: ${res.updated_fields.join(', ')}` })
      } else {
        setBanner({ message: 'Enrichment finished (no new fields).' })
      }
      refresh()
    },
    onError,
  })
  const saveM = useMutation({
    mutationFn: () =>
      updateProspect(prospectId, {
        company: draft.company.trim(),
        event_name: draft.event_name.trim(),
        email: draft.email.trim() || null,
        phone_raw: draft.phone_raw.trim(),
        website: draft.website.trim(),
        notes: draft.notes.trim(),
      }),
    onSuccess: () => {
      setEditing(false)
      setBanner({ message: 'Prospect updated.' })
      refresh()
    },
    onError,
  })

  const p = q.data

  return (
    <div className="space-y-6">
      <PageHeader
        title={p ? p.company || `Prospect #${prospectId}` : `Prospect #${prospectId}`}
        description="Review source context and quality signals before converting to a lead."
        actions={
          <>
            {p ? (
              <Button
                variant="outline"
                onClick={() => {
                  if (editing) {
                    setEditing(false)
                  } else {
                    setDraft({
                      company: p.company ?? '',
                      event_name: p.event_name ?? '',
                      email: p.email ?? '',
                      phone_raw: p.phone_raw ?? '',
                      website: p.website ?? '',
                      notes: p.notes ?? '',
                    })
                    setEditing(true)
                  }
                }}
              >
                {editing ? 'Cancel edit' : 'Edit'}
              </Button>
            ) : null}
            <Button variant="outline" asChild>
              <Link to="/prospects">Back to prospects</Link>
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      {q.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading prospect…</p>
      ) : p ? (
        <>
          {editing ? (
            <form
              className="space-y-4 rounded-lg border border-border bg-card p-5"
              onSubmit={(e) => {
                e.preventDefault()
                saveM.mutate()
              }}
            >
              <FormField label="Company">
                <Input value={draft.company} onChange={(e) => setDraft((d) => ({ ...d, company: e.target.value }))} />
              </FormField>
              <FormField label="Event">
                <Input value={draft.event_name} onChange={(e) => setDraft((d) => ({ ...d, event_name: e.target.value }))} />
              </FormField>
              <FormField label="Email">
                <Input type="email" value={draft.email} onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))} />
              </FormField>
              <FormField label="Phone">
                <Input value={draft.phone_raw} onChange={(e) => setDraft((d) => ({ ...d, phone_raw: e.target.value }))} />
              </FormField>
              <FormField label="Website">
                <Input value={draft.website} onChange={(e) => setDraft((d) => ({ ...d, website: e.target.value }))} />
              </FormField>
              <FormField label="Notes">
                <textarea
                  className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={draft.notes}
                  onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                />
              </FormField>
              <Button type="submit" disabled={saveM.isPending}>
                {saveM.isPending ? 'Saving…' : 'Save changes'}
              </Button>
            </form>
          ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <DetailField label="Status">
              <StatusBadge status={p.status} kind="prospect" />
            </DetailField>
            <DetailField label="Quality score">
              <ScoreBadge score={p.translation_need_score} label={p.score_label} />
            </DetailField>
            <DetailField label="Source">{p.source_name || '—'}</DetailField>
            <DetailField label="Company">{p.company || '—'}</DetailField>
            <DetailField label="Event">{p.event_name || '—'}</DetailField>
            <DetailField label="Email">{p.email || '—'}</DetailField>
            <DetailField label="Phone">{p.phone_raw || '—'}</DetailField>
            <DetailField label="Website">
              {p.website ? (
                <ExternalTextLink href={p.website}>{p.website}</ExternalTextLink>
              ) : (
                '—'
              )}
            </DetailField>
            <DetailField label="Source URL">
              {p.source_url ? (
                <ExternalTextLink href={p.source_url}>{p.source_url}</ExternalTextLink>
              ) : (
                '—'
              )}
            </DetailField>
          </div>
          )}

          <DuplicateMatchesPanel
            items={duplicatesQ.data?.items ?? []}
            basePath="/prospects"
            loading={duplicatesQ.isLoading}
          />

          {p.score_reasoning ? (
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm font-medium text-foreground">Why this prospect scored</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{p.score_reasoning}</p>
            </div>
          ) : null}

          {p.notes ? (
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm font-medium text-foreground">Notes</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{p.notes}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {p.source_url ? (
              <Button variant="secondary" disabled={enrichM.isPending} onClick={() => enrichM.mutate()}>
                {enrichM.isPending ? 'Enriching…' : 'Enrich from source'}
              </Button>
            ) : null}
            <Button disabled={p.status !== 'new' || contactedM.isPending} onClick={() => contactedM.mutate()}>
              Mark contacted
            </Button>
            <Button
              disabled={!['new', 'contacted'].includes(p.status) || convertM.isPending}
              onClick={() => convertM.mutate()}
            >
              Convert to lead
            </Button>
            <Button
              variant="outline"
              disabled={p.status === 'rejected' || rejectM.isPending}
              onClick={() => rejectM.mutate()}
            >
              Reject
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Prospect not found.</p>
      )}
    </div>
  )
}
