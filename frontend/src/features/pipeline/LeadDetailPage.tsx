import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { DuplicateMatchesPanel } from '@/features/pipeline/DuplicateMatchesPanel'
import { formatLeadValue } from '@/features/pipeline/leadUtils'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  getLead,
  getLeadDuplicates,
  leadMarkInterested,
  leadReject,
  leadSyncCrm,
  updateLead,
} from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DetailField } from '@/shared/components/DetailField'
import { ExternalTextLink, TextLink } from '@/shared/components/TextLink'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'

export function LeadDetailPage() {
  const params = useParams()
  const qc = useQueryClient()
  const leadId = Number(params.leadId)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({
    full_name: '',
    company: '',
    email: '',
    phone_raw: '',
    website: '',
    notes: '',
    lead_value: '',
  })

  const q = useQuery({
    queryKey: ['lead', leadId],
    queryFn: () => getLead(leadId),
    enabled: leadId > 0,
  })

  const duplicatesQ = useQuery({
    queryKey: ['lead-duplicates', leadId],
    queryFn: () => getLeadDuplicates(leadId),
    enabled: leadId > 0,
  })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['leads'] })
    void qc.invalidateQueries({ queryKey: ['lead', leadId] })
    void qc.invalidateQueries({ queryKey: ['lead-duplicates', leadId] })
  }

  const onError = (err: unknown) => setBanner({ error: getApiErrorMessage(err) })

  const interestedM = useMutation({
    mutationFn: () => leadMarkInterested(leadId),
    onSuccess: () => {
      setBanner({ message: 'Marked as interested.' })
      refresh()
    },
    onError,
  })
  const rejectM = useMutation({
    mutationFn: () => leadReject(leadId),
    onSuccess: () => {
      setBanner({ message: 'Lead rejected.' })
      refresh()
    },
    onError,
  })
  const syncM = useMutation({
    mutationFn: () => leadSyncCrm(leadId),
    onSuccess: () => {
      setBanner({ message: 'CRM sync queued.' })
      refresh()
    },
    onError,
  })
  const saveM = useMutation({
    mutationFn: () =>
      updateLead(leadId, {
        full_name: draft.full_name.trim(),
        company: draft.company.trim(),
        email: draft.email.trim() || null,
        phone_raw: draft.phone_raw.trim(),
        website: draft.website.trim(),
        notes: draft.notes.trim(),
        lead_value: draft.lead_value.trim() ? draft.lead_value.trim() : null,
      }),
    onSuccess: () => {
      setEditing(false)
      setBanner({ message: 'Lead updated.' })
      refresh()
    },
    onError,
  })

  const l = q.data

  return (
    <div className="space-y-6">
      <PageHeader
        title={l ? l.full_name || l.company || `Lead #${leadId}` : `Lead #${leadId}`}
        description="Qualify interest and sync complete records to CRM."
        actions={
          <>
            {l ? (
              <Button
                variant="outline"
                onClick={() => {
                  if (editing) {
                    setEditing(false)
                  } else {
                    setDraft({
                      full_name: l.full_name ?? '',
                      company: l.company ?? '',
                      email: l.email ?? '',
                      phone_raw: l.phone_raw ?? '',
                      website: l.website ?? '',
                      notes: l.notes ?? '',
                      lead_value: l.lead_value ?? '',
                    })
                    setEditing(true)
                  }
                }}
              >
                {editing ? 'Cancel edit' : 'Edit'}
              </Button>
            ) : null}
            <Button variant="outline" asChild>
              <Link to="/leads">Back to leads</Link>
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      {q.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading lead…</p>
      ) : l ? (
        <>
          {editing ? (
            <form
              className="space-y-4 rounded-lg border border-border bg-card p-5"
              onSubmit={(e) => {
                e.preventDefault()
                saveM.mutate()
              }}
            >
              <FormField label="Name">
                <Input value={draft.full_name} onChange={(e) => setDraft((d) => ({ ...d, full_name: e.target.value }))} />
              </FormField>
              <FormField label="Company">
                <Input value={draft.company} onChange={(e) => setDraft((d) => ({ ...d, company: e.target.value }))} />
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
              <FormField label="Lead value (USD)">
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  value={draft.lead_value}
                  onChange={(e) => setDraft((d) => ({ ...d, lead_value: e.target.value }))}
                />
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
                <StatusBadge status={l.status} kind="lead" />
              </DetailField>
              <DetailField label="Lead value">{formatLeadValue(l.lead_value)}</DetailField>
              <DetailField label="Source">{l.source_name || '—'}</DetailField>
              <DetailField label="Name">{l.full_name || '—'}</DetailField>
              <DetailField label="Company">{l.company || '—'}</DetailField>
              <DetailField label="Event">{l.event_name || '—'}</DetailField>
              <DetailField label="Email">{l.email || '—'}</DetailField>
              <DetailField label="Phone">{l.phone_raw || '—'}</DetailField>
              <DetailField label="Website">
                {l.website ? (
                  <ExternalTextLink href={l.website}>{l.website}</ExternalTextLink>
                ) : (
                  '—'
                )}
              </DetailField>
              {l.prospect_id ? (
                <DetailField label="From prospect">
                  <TextLink to={`/prospects/${l.prospect_id}`}>Prospect #{l.prospect_id}</TextLink>
                </DetailField>
              ) : null}
            </div>
          )}

          <DuplicateMatchesPanel items={duplicatesQ.data?.items ?? []} basePath="/leads" loading={duplicatesQ.isLoading} />

          {!editing && l.notes ? (
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm font-medium text-foreground">Notes</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{l.notes}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button disabled={l.status !== 'contacted' || interestedM.isPending} onClick={() => interestedM.mutate()}>
              Mark interested
            </Button>
            <Button disabled={l.status !== 'interested' || syncM.isPending} onClick={() => syncM.mutate()}>
              Sync to CRM
            </Button>
            <Button
              variant="outline"
              disabled={['rejected', 'synced'].includes(l.status) || rejectM.isPending}
              onClick={() => rejectM.mutate()}
            >
              Reject
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Lead not found.</p>
      )}
    </div>
  )
}
