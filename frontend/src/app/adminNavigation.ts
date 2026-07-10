import {
  Activity,
  BarChart3,
  Database,
  Globe2,
  Home,
  LayoutDashboard,
  PlayCircle,
  Radio,
  Settings,
  Shield,
  Sparkles,
  Target,
  UserCircle,
  Users,
  Wrench,
} from 'lucide-react'

import type { NavSection } from '@/app/navigation'

export const ADMIN_NAV_SECTIONS: NavSection[] = [
  {
    label: 'Overview',
    items: [
      { to: '/admin', label: 'Admin home', icon: LayoutDashboard, end: true },
      { to: '/admin/profile', label: 'Profile', icon: UserCircle },
    ],
  },
  {
    label: 'Scraper',
    items: [
      { to: '/admin/scraper', label: 'Scraper overview', icon: Wrench, end: true },
      { to: '/admin/scraper/targets', label: 'Scrape targets', icon: Target },
      { to: '/admin/scraper/runs', label: 'Scrape runs', icon: PlayCircle },
    ],
  },
  {
    label: 'Crawler',
    items: [
      { to: '/admin/crawler', label: 'Crawler overview', icon: Home, end: true },
      { to: '/admin/crawler/sources', label: 'Crawl sources', icon: Database },
      { to: '/admin/crawler/domains', label: 'Domain queue', icon: Globe2 },
      { to: '/admin/crawler/runs', label: 'Crawl runs', icon: Radio },
    ],
  },
  {
    label: 'Management',
    items: [
      { to: '/admin/users', label: 'Users & roles', icon: Users },
      { to: '/admin/ai-search', label: 'AI search', icon: Sparkles },
      { to: '/admin/pipeline', label: 'Pipeline', icon: Wrench },
      { to: '/admin/quality', label: 'Lead quality', icon: BarChart3 },
    ],
  },
  {
    label: 'Security & Health',
    items: [
      { to: '/admin/monitoring', label: 'Monitoring', icon: Activity },
      { to: '/admin/audit', label: 'Audit log', icon: Shield },
      { to: '/admin/settings', label: 'Settings', icon: Settings },
    ],
  },
]
