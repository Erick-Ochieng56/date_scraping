import { cn } from '@/lib/utils'

type SectionEyebrowProps = {
  children: React.ReactNode
  className?: string
}

export function SectionEyebrow({ children, className }: SectionEyebrowProps) {
  return (
    <p className={cn('text-xs font-medium tracking-wide text-muted-foreground', className)}>{children}</p>
  )
}
