import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import { createLead } from '@/shared/api/pipeline'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'

export function LeadCreatePage() {
  const navigate = useNavigate()
  const [banner, setBanner] = useState<{ error?: string }>({})
  const [fullName, setFullName] = useState('')
  const [company, setCompany] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [website, setWebsite] = useState('')
  const [eventName, setEventName] = useState('')
  const [status, setStatus] = useState('contacted')

  const createM = useMutation({
    mutationFn: () =>
      createLead({
        full_name: fullName.trim(),
        company: company.trim(),
        email: email.trim() || null,
        phone_raw: phone.trim(),
        website: website.trim(),
        event_name: eventName.trim(),
        status,
      }),
    onSuccess: (l) => navigate(`/leads/${l.id}`),
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader
        title="Add lead"
        description="Manually create a lead for CRM qualification."
        actions={
          <Button variant="outline" asChild>
            <Link to="/leads">Cancel</Link>
          </Button>
        }
      />
      <AlertBanner error={banner.error} />
      <form
        className="space-y-4 rounded-lg border border-border bg-card p-5"
        onSubmit={(e) => {
          e.preventDefault()
          createM.mutate()
        }}
      >
        <FormField label="Full name">
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </FormField>
        <FormField label="Company">
          <Input value={company} onChange={(e) => setCompany(e.target.value)} required />
        </FormField>
        <FormField label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField label="Phone">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </FormField>
        <FormField label="Website">
          <Input type="url" value={website} onChange={(e) => setWebsite(e.target.value)} />
        </FormField>
        <FormField label="Event">
          <Input value={eventName} onChange={(e) => setEventName(e.target.value)} />
        </FormField>
        <FormField label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="contacted">Contacted</option>
            <option value="interested">Interested</option>
          </Select>
        </FormField>
        <Button type="submit" disabled={createM.isPending || !company.trim()}>
          {createM.isPending ? 'Creating…' : 'Create lead'}
        </Button>
      </form>
    </div>
  )
}
