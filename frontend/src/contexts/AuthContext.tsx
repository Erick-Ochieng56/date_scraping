import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'

import {
  fetchMe,
  loginRequest,
  logoutRequest,
  type MeResponse,
} from '@/lib/api/auth'

type AuthContextValue = {
  me: MeResponse | undefined
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()

  const { data: me, isPending } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchMe,
    staleTime: 30_000,
  })

  const loginMut = useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) => {
      const res = await loginRequest(username, password)
      if (!res.success) throw new Error(res.error ?? 'Login failed')
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })

  const logoutMut = useMutation({
    mutationFn: logoutRequest,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })

  const login = useCallback(
    async (username: string, password: string) => {
      await loginMut.mutateAsync({ username, password })
    },
    [loginMut]
  )

  const logout = useCallback(async () => {
    await logoutMut.mutateAsync()
  }, [logoutMut])

  const value = useMemo(
    () => ({
      me,
      isLoading: isPending,
      login,
      logout,
    }),
    [me, isPending, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
