import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'

const ITEMS = [
  { to: '/crawler', label: 'Overview', end: true },
  { to: '/crawler/discover', label: 'Discover' },
  { to: '/crawler/domains', label: 'Domains' },
  { to: '/crawler/runs', label: 'Runs' },
  { to: '/crawler/schedules', label: 'Schedules' },
  { to: '/crawler/ai-search', label: 'AI search' },
] as const

export function CrawlerSubNav() {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-border pb-2">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={'end' in item ? item.end : false}
          className={({ isActive }) =>
            cn(
              'rounded-md border-l-2 px-3 py-1.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-primary bg-muted text-foreground'
                : 'border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground'
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
