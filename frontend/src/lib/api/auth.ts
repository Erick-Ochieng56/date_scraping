import { isAxiosError } from 'axios'

import { apiClient } from '@/lib/api/client'

export type MeResponse =
  | { authenticated: false; reason?: string }
  | { authenticated: true; role: 'admin'; username: string }
  | { authenticated: true; role: 'staff'; username: string }

export async function fetchMe(): Promise<MeResponse> {
  const { data } = await apiClient.get<MeResponse>('/dashboard/api/auth/me/')
  return data
}

export async function loginRequest(username: string, password: string) {
  const { data } = await apiClient.post<{ success: boolean; error?: string }>(
    '/dashboard/api/auth/login/',
    { username, password }
  )
  return data
}

export async function logoutRequest() {
  await apiClient.post('/dashboard/api/auth/logout/')
}

export function loginErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const d = err.response?.data as { error?: string; detail?: string } | undefined
    return d?.error ?? d?.detail ?? err.message ?? 'Login failed'
  }
  if (err instanceof Error) return err.message
  return 'Login failed'
}
