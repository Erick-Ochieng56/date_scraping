import { apiClient } from '@/lib/api/client'

export type UserProfile = {
  id: number
  username: string
  email: string
  role: 'admin' | 'staff' | 'none'
  is_superuser: boolean
  last_login: string | null
  date_joined: string | null
}

export async function fetchProfile() {
  const { data } = await apiClient.get<{ success: boolean; data: UserProfile }>('/dashboard/api/v1/profile/')
  return data.data
}

export async function updateProfile(payload: { email: string }) {
  const { data } = await apiClient.patch<{ success: boolean; data: UserProfile }>(
    '/dashboard/api/v1/profile/',
    payload
  )
  return data.data
}

export async function changePassword(payload: { current_password: string; new_password: string }) {
  const { data } = await apiClient.post<{ success: boolean; data: { message: string } }>(
    '/dashboard/api/v1/profile/change-password/',
    payload
  )
  return data.data
}
