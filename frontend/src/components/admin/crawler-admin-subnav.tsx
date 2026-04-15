import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'

type SubNavItem = {
  readonly to: string
  readonly label: string
  readonly end?: boolean
}

const ITEMS: readonly SubNavItem[] = [
  { to: '/admin/crawler', label: 'Overview', end: true },
  { to: '/admin/crawler/sources', label: 'Sources' },
  { to: '/admin/crawler/domains', label: 'Domains' },
  { to: '/admin/crawler/runs', label: 'Runs' },
]

export function CrawlerAdminSubNav() {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-border pb-2">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end ?? false}
          className={({ isActive }) =>
            cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
