import type { ReactNode } from 'react'

type DetailFieldProps = {
  label: string
  children: ReactNode
}

export function DetailField({ label, children }: DetailFieldProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
      <div className="mt-1 break-words text-sm font-medium text-foreground">{children}</div>
    </div>
  )
}
