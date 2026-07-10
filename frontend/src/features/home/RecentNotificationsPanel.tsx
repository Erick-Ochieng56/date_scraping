import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { Link } from 'react-router-dom'

import { notificationKeys } from '@/shared/notifications/queryKeys'
import { fetchNotifications, markNotificationRead } from '@/shared/api/notifications'
import { NotificationListItem } from '@/shared/components/NotificationListItem'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { TextLink } from '@/shared/components/TextLink'

export function RecentNotificationsPanel() {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: notificationKeys.list(5),
    queryFn: () => fetchNotifications({ limit: 5 }),
    refetchInterval: 30_000,
  })

  const markReadM = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: notificationKeys.all }),
  })

  const unread = q.data?.unread_count ?? 0
  const items = q.data?.items ?? []
  const unreadItems = items.filter((n) => !n.read)

  if (!q.isLoading && unread === 0) {
    return null
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <SectionEyebrow>Recent notifications</SectionEyebrow>
        <TextLink to="/notifications">View all →</TextLink>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        {q.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading notifications…</p>
        ) : unreadItems.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Bell className="size-4" aria-hidden />
            {unread} unread — open the notification center to review.
          </div>
        ) : (
          <ul className="space-y-2">
            {unreadItems.slice(0, 3).map((n) => (
              <NotificationListItem
                key={n.id}
                item={n}
                compact
                onMarkRead={(id) => markReadM.mutate(id)}
              />
            ))}
          </ul>
        )}
        {unread > 3 ? (
          <p className="mt-3 text-xs text-muted-foreground">
            +{unread - 3} more unread.{' '}
            <Link className="text-primary hover:underline" to="/notifications">
              Open notifications
            </Link>
          </p>
        ) : null}
      </div>
    </section>
  )
}
