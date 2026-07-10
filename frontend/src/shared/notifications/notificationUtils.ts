import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { NotificationItem } from '@/shared/api/types'

export function notificationIcon(type: string): LucideIcon {
  switch (type) {
    case 'success':
      return CheckCircle2
    case 'warning':
      return AlertTriangle
    case 'error':
      return AlertCircle
    default:
      return Info
  }
}

export function notificationAccentClass(type: string): string {
  switch (type) {
    case 'success':
      return 'text-emerald-600 dark:text-emerald-400'
    case 'warning':
      return 'text-amber-600 dark:text-amber-400'
    case 'error':
      return 'text-red-600 dark:text-red-400'
    default:
      return 'text-sky-600 dark:text-sky-400'
  }
}

export function formatNotificationTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = Date.now()
  const diffMs = now - date.getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}d ago`
  return date.toLocaleDateString()
}

export function notificationLinkLabel(item: NotificationItem): string {
  if (!item.link_url) return ''
  if (item.link_url.includes('/runs/')) return 'View run'
  if (item.link_url.includes('/crawler/')) return 'View crawl'
  if (item.link_url.includes('/targets')) return 'Open targets'
  if (item.link_url.includes('/prospects')) return 'View prospects'
  if (item.link_url.includes('/leads')) return 'View leads'
  return 'Open'
}
