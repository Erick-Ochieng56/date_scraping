import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { notificationKeys } from '@/shared/notifications/queryKeys'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/shared/api/notifications'
import { NotificationListItem } from '@/shared/components/NotificationListItem'

export function NotificationBell() {
  const { me } = useAuth()
  const qc = useQueryClient()
  const detailsRef = useRef<HTMLDetailsElement>(null)
  const allHref = me?.authenticated && me.role === 'admin' ? '/admin/notifications' : '/notifications'

  const q = useQuery({
    queryKey: notificationKeys.list(12),
    queryFn: () => fetchNotifications({ limit: 12 }),
    refetchInterval: 30_000,
  })

  const markReadM = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: notificationKeys.all }),
  })

  const markAllM = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => void qc.invalidateQueries({ queryKey: notificationKeys.all }),
  })

  const unread = q.data?.unread_count ?? 0
  const items = q.data?.items ?? []

  useEffect(() => {
    const el = detailsRef.current
    if (!el) return
    const closeOnOutside = (event: MouseEvent) => {
      if (!el.open) return
      const target = event.target as Node
      if (!el.contains(target)) el.open = false
    }
    document.addEventListener('click', closeOnOutside)
    return () => document.removeEventListener('click', closeOnOutside)
  }, [])

  const closePanel = () => {
    if (detailsRef.current) detailsRef.current.open = false
  }

  return (
    <div className="relative">
      <details ref={detailsRef} className="group">
        <summary className="list-none [&::-webkit-details-marker]:hidden">
          <Button type="button" variant="ghost" size="icon" className="relative" aria-label="Notifications">
            <Bell className="size-5" />
            {unread > 0 ? (
              <span className="absolute right-1 top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                {unread > 9 ? '9+' : unread}
              </span>
            ) : null}
          </Button>
        </summary>
        <div className="absolute right-0 z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-lg border border-border bg-card p-2 shadow-lg">
          <div className="flex items-center justify-between gap-2 px-2 py-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Notifications</p>
            <div className="flex items-center gap-2">
              {unread > 0 ? (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline disabled:opacity-50"
                  disabled={markAllM.isPending}
                  onClick={() => markAllM.mutate()}
                >
                  Mark all read
                </button>
              ) : null}
              <Link className="text-xs text-primary hover:underline" to={allHref} onClick={closePanel}>
                View all
              </Link>
            </div>
          </div>
          {q.isLoading ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">No notifications yet.</p>
          ) : (
            <ul className="max-h-80 space-y-1 overflow-y-auto">
              {items.map((n) => (
                <NotificationListItem
                  key={n.id}
                  item={n}
                  compact
                  onMarkRead={(id) => markReadM.mutate(id)}
                  onNavigate={closePanel}
                />
              ))}
            </ul>
          )}
        </div>
      </details>
    </div>
  )
}
