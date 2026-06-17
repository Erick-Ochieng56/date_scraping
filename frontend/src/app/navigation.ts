import { LayoutDashboard, PlayCircle, Target, Users, UserPlus, Globe } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  /** When true, NavLink matches this route exactly (no prefix match). */
  end?: boolean
}

export type NavSection = {
  label: string
  items: NavItem[]
}

/** Scraper-facing nav only (admin-only Django pages are not linked here). Paths are top-level to avoid /dashboard clashes with the API. */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Scraper',
    items: [
      { to: '/targets', label: 'Targets', icon: Target },
      { to: '/runs', label: 'Scrape runs', icon: PlayCircle },
    ],
  },
  {
    label: 'Crawler',
    items: [{ to: '/crawler', label: 'Crawler', icon: Globe }],
  },
  {
    label: 'Pipeline',
    items: [
      { to: '/prospects', label: 'Prospects', icon: UserPlus },
      { to: '/leads', label: 'Leads', icon: Users },
    ],
  },
]
