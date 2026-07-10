export function crawlTriggerLabel(trigger: string) {
  if (trigger === 'scheduled') return 'Scheduled'
  if (trigger === 'manual') return 'Manual'
  if (trigger === 'session') return 'Session'
  return trigger
}

export function truncateText(s: string, max = 72) {
  if (!s) return ''
  return s.length <= max ? s : `${s.slice(0, max)}…`
}
