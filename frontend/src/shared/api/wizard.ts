import { isAxiosError } from 'axios'

import { apiClient } from '@/lib/api/client'

export type WizardSuggestedConfig = {
  name: string
  target_type: string
  start_url: string
  run_every_minutes: number
  enabled: boolean
  config: Record<string, unknown>
}

export type WizardDetectResponse = {
  success: boolean
  platform: string
  detected: boolean
  suggested_config: WizardSuggestedConfig
  error?: string
}

export type WizardCreatePayload = {
  url: string
  name?: string
  target_type?: string
  run_every_minutes?: number
  enabled?: boolean
  config?: Record<string, unknown>
}

export type WizardCreateResponse = {
  success: boolean
  target_id?: number
  name?: string
  platform?: string
  message?: string
  error?: string
  existing?: boolean
}

export class WizardConflictError extends Error {
  targetId: number

  constructor(message: string, targetId: number) {
    super(message)
    this.name = 'WizardConflictError'
    this.targetId = targetId
  }
}

export async function wizardDetectPlatform(url: string): Promise<WizardDetectResponse> {
  const { data } = await apiClient.get<WizardDetectResponse>('/dashboard/wizard/detect-platform/', {
    params: { url: url.trim() },
  })
  return data
}

export async function wizardCreateTarget(payload: WizardCreatePayload): Promise<WizardCreateResponse> {
  try {
    const { data } = await apiClient.post<WizardCreateResponse>('/dashboard/wizard/create-target/', payload)
    return data
  } catch (err) {
    if (isAxiosError(err) && err.response?.status === 409) {
      const d = err.response.data as WizardCreateResponse
      const targetId = d.target_id
      if (targetId != null) {
        throw new WizardConflictError(d.error ?? 'A target with this name already exists.', targetId)
      }
    }
    throw err
  }
}
