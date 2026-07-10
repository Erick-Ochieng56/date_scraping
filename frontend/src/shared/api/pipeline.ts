import { apiClient } from '@/lib/api/client'

import type { DuplicateMatch, Lead, Paginated, Prospect } from './types'

export type ProspectListParams = {
  page?: number
  page_size?: number
  status?: string
  search?: string
  source?: string
  min_score?: number
  sort?: 'created_at' | 'score'
}

export type LeadListParams = {
  page?: number
  page_size?: number
  status?: string
  search?: string
}

export type PipelineExportParams = {
  status?: string
  search?: string
  source?: string
  min_score?: number
  date_from?: string
  date_to?: string
}

function buildExportQuery(params?: PipelineExportParams): string {
  if (!params) return ''
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.search?.trim()) qs.set('search', params.search.trim())
  if (params.source?.trim()) qs.set('source', params.source.trim())
  if (params.min_score != null) qs.set('min_score', String(params.min_score))
  if (params.date_from) qs.set('date_from', params.date_from)
  if (params.date_to) qs.set('date_to', params.date_to)
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export async function listProspects(params?: ProspectListParams) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Prospect> }>('/dashboard/api/v1/prospects/', {
    params,
  })
  return data.data
}

export type ProspectCreatePayload = {
  event_name?: string
  company?: string
  email?: string | null
  phone_raw?: string
  website?: string
  source_name?: string
  source_url?: string
  notes?: string
  status?: string
}

export async function createProspect(payload: ProspectCreatePayload) {
  const { data } = await apiClient.post<{ success: boolean; data: Prospect }>('/dashboard/api/v1/prospects/', payload)
  return data.data
}

export async function prospectsBulkContacted(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/prospects/bulk/contacted/',
    { prospect_ids }
  )
  return data
}

export async function prospectsBulkConvert(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number; errors?: string[] }>(
    '/dashboard/api/v1/prospects/bulk/convert/',
    { prospect_ids }
  )
  return data
}

export async function prospectsBulkReject(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/prospects/bulk/reject/',
    { prospect_ids }
  )
  return data
}

export async function getProspect(prospectId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Prospect }>(`/dashboard/api/v1/prospects/${prospectId}/`)
  return data.data
}

export type ProspectUpdatePayload = Partial<ProspectCreatePayload>

export async function updateProspect(prospectId: number, payload: ProspectUpdatePayload) {
  const { data } = await apiClient.patch<{ success: boolean; data: Prospect }>(
    `/dashboard/api/v1/prospects/${prospectId}/`,
    payload
  )
  return data.data
}

export async function getProspectDuplicates(prospectId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: { items: DuplicateMatch[]; total: number } }>(
    `/dashboard/api/v1/prospects/${prospectId}/duplicates/`
  )
  return data.data
}

export async function prospectMarkContacted(prospectId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/prospects/${prospectId}/mark-contacted/`)
  return data
}

export async function prospectConvert(prospectId: number) {
  const { data } = await apiClient.post<{ success: boolean; lead_id?: number }>(
    `/dashboard/api/v1/prospects/${prospectId}/convert/`
  )
  return data
}

export async function prospectReject(prospectId: number, reason?: string) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/prospects/${prospectId}/reject/`, {
    reason,
  })
  return data
}

export async function prospectEnrich(
  prospectId: number,
  options?: { platform?: string; use_playwright?: boolean; force?: boolean }
) {
  const { data } = await apiClient.post<{
    success: boolean
    skipped?: boolean
    updated_fields?: string[]
    data: Prospect
  }>(`/dashboard/api/v1/prospects/${prospectId}/enrich/`, options ?? {})
  return data
}

export async function listLeads(params?: LeadListParams) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Lead> }>('/dashboard/api/v1/leads/', {
    params,
  })
  return data.data
}

export type LeadCreatePayload = {
  full_name?: string
  company?: string
  email?: string | null
  phone_raw?: string
  website?: string
  position?: string
  event_name?: string
  address?: string
  city?: string
  state?: string
  country_code?: string
  notes?: string
  status?: string
  lead_value?: number | string | null
}

export async function createLead(payload: LeadCreatePayload) {
  const { data } = await apiClient.post<{ success: boolean; data: Lead }>('/dashboard/api/v1/leads/', payload)
  return data.data
}

export async function leadsBulkInterested(lead_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/leads/bulk/interested/',
    { lead_ids }
  )
  return data
}

export async function leadsBulkReject(lead_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/leads/bulk/reject/',
    { lead_ids }
  )
  return data
}

export async function leadsBulkSyncCrm(lead_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number; message?: string }>(
    '/dashboard/api/v1/leads/bulk/sync-crm/',
    { lead_ids }
  )
  return data
}

export async function getLead(leadId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Lead }>(`/dashboard/api/v1/leads/${leadId}/`)
  return data.data
}

export type LeadUpdatePayload = Partial<LeadCreatePayload>

export async function updateLead(leadId: number, payload: LeadUpdatePayload) {
  const { data } = await apiClient.patch<{ success: boolean; data: Lead }>(`/dashboard/api/v1/leads/${leadId}/`, payload)
  return data.data
}

export async function getLeadDuplicates(leadId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: { items: DuplicateMatch[]; total: number } }>(
    `/dashboard/api/v1/leads/${leadId}/duplicates/`
  )
  return data.data
}

export async function leadMarkInterested(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/leads/${leadId}/mark-interested/`)
  return data
}

export async function leadReject(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/leads/${leadId}/reject/`)
  return data
}

export async function leadSyncCrm(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean; task_id?: string }>(`/dashboard/api/v1/leads/${leadId}/sync-crm/`)
  return data
}

export function prospectsExportUrl(params?: PipelineExportParams): string {
  return `/dashboard/export/prospects/csv${buildExportQuery(params)}`
}

export function leadsExportUrl(params?: PipelineExportParams): string {
  return `/dashboard/export/leads/csv${buildExportQuery(params)}`
}
