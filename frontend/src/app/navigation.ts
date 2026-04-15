import { Globe, Home, LayoutDashboard, PlayCircle, Radio, Search, Sparkles, Target, Users, UserPlus } from 'lucide-react'
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
    items: [
      { to: '/crawler', label: 'Crawler home', icon: Home },
      { to: '/crawler/discover', label: 'Discover', icon: Search },
      { to: '/crawler/domains', label: 'Domains', icon: Globe },
      { to: '/crawler/runs', label: 'Crawl runs', icon: Radio },
      { to: '/crawler/ai-search', label: 'AI search', icon: Sparkles },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      { to: '/prospects', label: 'Prospects', icon: UserPlus },
      { to: '/leads', label: 'Leads', icon: Users },
    ],
  },
]
