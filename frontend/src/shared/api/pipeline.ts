import { apiClient } from '@/lib/api/client'

import type { Lead, Paginated, Prospect, ProspectDetail } from './types'

export async function listProspects(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Prospect> }>('/dashboard/api/v1/prospects/', {
    params,
  })
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
  const { data } = await apiClient.get<{ success: boolean; data: ProspectDetail }>(
    `/dashboard/api/v1/prospects/${prospectId}/`
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

export async function listLeads(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Lead> }>('/dashboard/api/v1/leads/', {
    params,
  })
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

export async function getLead(leadId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Lead }>(`/dashboard/api/v1/leads/${leadId}/`)
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

export function prospectsExportUrl(): string {
  return '/dashboard/export/prospects/csv/'
}

export function leadsExportUrl(): string {
  return '/dashboard/export/leads/csv/'
}
