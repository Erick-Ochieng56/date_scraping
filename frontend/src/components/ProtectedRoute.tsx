import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { SessionLoadingFallback } from '@/components/SessionLoadingFallback'
import { useAuth } from '@/contexts/AuthContext'

type Role = 'staff' | 'admin'

export function ProtectedRoute({ children, allowRoles }: { children: ReactNode; allowRoles: Role[] }) {
  const { me, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <SessionLoadingFallback />
  }

  if (!me?.authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (!allowRoles.includes(me.role)) {
    return <Navigate to={me.role === 'admin' ? '/admin' : '/'} replace />
  }

  return <>{children}</>
}
