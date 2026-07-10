import type { Lead } from '@/shared/api/types'

export function isLeadCrmReady(lead: Lead): boolean {
  const hasEmail = Boolean(lead.email?.trim())
  const hasCompany = Boolean(lead.company?.trim())
  const hasContact = Boolean(lead.phone_raw?.trim() || lead.full_name?.trim())
  return hasEmail && hasCompany && hasContact
}

export function formatLeadValue(value: string | null | undefined): string {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return value
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num)
}

const MATCH_LABELS: Record<string, string> = {
  same_payload_hash: 'Same crawl payload',
  same_email: 'Same email',
  same_website: 'Same website',
  same_prospect: 'Same source prospect',
  similar: 'Similar record',
}

export function duplicateMatchLabel(reason: string): string {
  return MATCH_LABELS[reason] ?? reason
}
