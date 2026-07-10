import { Link, useNavigate } from 'react-router-dom'

import { cn } from '@/lib/utils'
import type { NotificationItem } from '@/shared/api/types'
import {
  formatNotificationTime,
  notificationAccentClass,
  notificationIcon,
  notificationLinkLabel,
} from '@/shared/notifications/notificationUtils'

type Props = {
  item: NotificationItem
  compact?: boolean
  onMarkRead?: (id: number) => void
  onNavigate?: () => void
}

export function NotificationListItem({ item, compact = false, onMarkRead, onNavigate }: Props) {
  const navigate = useNavigate()
  const Icon = notificationIcon(item.type)

  const handleOpen = () => {
    if (!item.read) onMarkRead?.(item.id)
    if (item.link_url) {
      navigate(item.link_url)
      onNavigate?.()
    }
  }

  return (
    <li
      className={cn(
        'rounded-md border border-transparent px-2 py-2',
        !item.read && 'border-border bg-muted/50',
        item.link_url && 'cursor-pointer hover:bg-muted/40'
      )}
      onClick={item.link_url ? handleOpen : undefined}
      onKeyDown={
        item.link_url
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                handleOpen()
              }
            }
          : undefined
      }
      role={item.link_url ? 'button' : undefined}
      tabIndex={item.link_url ? 0 : undefined}
    >
      <div className="flex gap-2">
        <Icon className={cn('mt-0.5 size-4 shrink-0', notificationAccentClass(item.type))} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className={cn('font-medium text-foreground', compact ? 'text-sm' : 'text-sm')}>{item.title}</p>
            {item.created_at ? (
              <span className="shrink-0 text-xs text-tertiary">{formatNotificationTime(item.created_at)}</span>
            ) : null}
          </div>
          <p className={cn('text-muted-foreground', compact ? 'text-xs' : 'text-sm')}>{item.message}</p>
          <div className="mt-1.5 flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
            {item.link_url ? (
              <Link
                className="text-xs font-medium text-primary hover:underline"
                to={item.link_url}
                onClick={() => {
                  if (!item.read) onMarkRead?.(item.id)
                  onNavigate?.()
                }}
              >
                {notificationLinkLabel(item)}
              </Link>
            ) : null}
            {!item.read && onMarkRead ? (
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => onMarkRead(item.id)}
              >
                Mark read
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  )
}
