import { LayoutDashboard, PlayCircle, Sparkles, Target, Users, UserPlus, Globe } from 'lucide-react'
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

/**
 * Staff-facing nav only (admin-only Django pages are not linked here). Paths are
 * top-level to avoid /dashboard clashes with the API.
 *
 * Grouping and labels per UI_REDESIGN_PLAN.md Phase 3, adapted for decision #1:
 * staff keep direct access to the crawler and site-check pages (not hidden
 * behind an "Automation" curtain), so they're grouped with Find new leads
 * under one "Find leads" section instead of collapsed away.
 */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Home', icon: LayoutDashboard }],
  },
  {
    label: 'Find leads',
    items: [
      { to: '/find-leads', label: 'Find new leads', icon: Sparkles },
      { to: '/crawler', label: 'Web crawler', icon: Globe },
      { to: '/targets', label: 'Sites we check', icon: Target },
      { to: '/runs', label: 'Check history', icon: PlayCircle },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      { to: '/prospects', label: 'Review queue', icon: UserPlus },
      { to: '/leads', label: 'My leads', icon: Users },
    ],
  },
]
