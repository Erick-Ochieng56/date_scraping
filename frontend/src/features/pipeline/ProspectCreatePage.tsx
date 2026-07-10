import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import { createProspect } from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'

export function ProspectCreatePage() {
  const navigate = useNavigate()
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [company, setCompany] = useState('')
  const [eventName, setEventName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [website, setWebsite] = useState('')
  const [sourceName, setSourceName] = useState('manual')
  const [notes, setNotes] = useState('')

  const createM = useMutation({
    mutationFn: () =>
      createProspect({
        company: company.trim(),
        event_name: eventName.trim(),
        email: email.trim() || null,
        phone_raw: phone.trim(),
        website: website.trim(),
        source_name: sourceName.trim() || 'manual',
        notes: notes.trim(),
        status: 'new',
      }),
    onSuccess: (p) => navigate(`/prospects/${p.id}`),
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader
        title="Add prospect"
        description="Manually add a discovery record before contacting or converting."
        actions={
          <Button variant="outline" asChild>
            <Link to="/prospects">Cancel</Link>
          </Button>
        }
      />
      <AlertBanner message={banner.message} error={banner.error} />
      <form
        className="space-y-4 rounded-lg border border-border bg-card p-5"
        onSubmit={(e) => {
          e.preventDefault()
          createM.mutate()
        }}
      >
        <FormField label="Company">
          <Input value={company} onChange={(e) => setCompany(e.target.value)} required />
        </FormField>
        <FormField label="Event name">
          <Input value={eventName} onChange={(e) => setEventName(e.target.value)} />
        </FormField>
        <FormField label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField label="Phone">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </FormField>
        <FormField label="Website">
          <Input type="url" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://..." />
        </FormField>
        <FormField label="Source">
          <Select value={sourceName} onChange={(e) => setSourceName(e.target.value)}>
            <option value="manual">Manual entry</option>
            <option value="referral">Referral</option>
            <option value="event">Event</option>
            <option value="other">Other</option>
          </Select>
        </FormField>
        <FormField label="Notes">
          <textarea
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </FormField>
        <Button type="submit" disabled={createM.isPending || !company.trim()}>
          {createM.isPending ? 'Creating…' : 'Create prospect'}
        </Button>
      </form>
    </div>
  )
}
