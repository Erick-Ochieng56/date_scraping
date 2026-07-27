import { apiClient } from '@/lib/api/client'

export type UserProfile = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'staff' | null
  date_joined: string | null
  last_login: string | null
}

export async function getProfile() {
  const { data } = await apiClient.get<{ success: boolean; data: UserProfile }>(
    '/dashboard/api/auth/profile/'
  )
  return data
}

export async function updateProfile(payload: { first_name?: string; last_name?: string; email?: string }) {
  const { data } = await apiClient.patch<{ success: boolean; data: UserProfile; error?: string }>(
    '/dashboard/api/auth/profile/',
    payload
  )
  return data
}

export async function changePassword(payload: { current_password: string; new_password: string }) {
  const { data } = await apiClient.post<{ success: boolean; error?: string }>(
    '/dashboard/api/auth/profile/password/',
    payload
  )
  return data
}
