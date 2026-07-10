import { Link, type LinkProps } from 'react-router-dom'

import { cn } from '@/lib/utils'

type TextLinkProps = LinkProps & {
  className?: string
}

export function TextLink({ className, ...props }: TextLinkProps) {
  return <Link className={cn('font-medium text-info hover:underline', className)} {...props} />
}

type ExternalTextLinkProps = React.ComponentProps<'a'> & {
  className?: string
}

export function ExternalTextLink({ className, ...props }: ExternalTextLinkProps) {
  return (
    <a
      className={cn('font-medium text-info hover:underline', className)}
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  )
}
