import { StatusBadge } from '@/shared/components/StatusBadge'

export function RunStatusBadge({ status, display }: { status: string; display?: string }) {
  return <StatusBadge status={display ?? status} kind="run" />
}
