import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { notificationKeys } from '@/shared/notifications/queryKeys'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/shared/api/notifications'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { NotificationListItem } from '@/shared/components/NotificationListItem'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'

const FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread only' },
] as const

export function NotificationsPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const q = useQuery({
    queryKey: notificationKeys.list(50),
    queryFn: () => fetchNotifications({ limit: 50 }),
    refetchInterval: 30_000,
  })

  const markReadM = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: notificationKeys.all }),
    onError: () => setBanner({ error: 'Could not mark notification as read.' }),
  })

  const markAllM = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: (data) => {
      setBanner({ message: `Marked ${data.marked ?? 0} notification(s) as read.` })
      void qc.invalidateQueries({ queryKey: notificationKeys.all })
    },
    onError: () => setBanner({ error: 'Could not mark all as read.' }),
  })

  const items = (q.data?.items ?? []).filter((n) => (filter === 'unread' ? !n.read : true))
  const unread = q.data?.unread_count ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notifications"
        description="Scrape results, crawl sessions, and other pipeline events for your account."
        actions={
          <>
            <Button variant="outline" onClick={() => void q.refetch()}>
              Refresh
            </Button>
            {unread > 0 ? (
              <Button variant="outline" disabled={markAllM.isPending} onClick={() => markAllM.mutate()}>
                Mark all read ({unread})
              </Button>
            ) : null}
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Show
          <Select
            value={filter}
            onChange={(e) => setFilter(e.target.value as 'all' | 'unread')}
            className="min-w-[8rem]"
            aria-label="Notification filter"
          >
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </label>
        <span className="text-sm text-tertiary">
          {unread > 0 ? `${unread} unread` : 'All caught up'}
        </span>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        {q.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading notifications…</p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <Bell className="size-8 text-muted-foreground/60" aria-hidden />
            <p className="text-sm text-muted-foreground">
              {filter === 'unread' ? 'No unread notifications.' : 'No notifications yet.'}
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((n) => (
              <NotificationListItem key={n.id} item={n} onMarkRead={(id) => markReadM.mutate(id)} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
