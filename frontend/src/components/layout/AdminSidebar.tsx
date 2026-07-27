import { LogOut } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'

import { ADMIN_NAV_SECTIONS } from '@/app/adminNavigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/shared/components/ThemeToggle'

export function AdminSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { logout, me } = useAuth()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
    onNavigate?.()
  }

  return (
    <div className="flex h-full flex-col gap-6 px-3 py-4">
      <div className="flex items-center gap-2 px-2">
        <img src="/atericlogo.svg" alt="" className="size-9 shrink-0 rounded-md bg-white/10 p-1" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-sidebar-foreground">Ateric Leads</p>
          <p className="truncate text-xs text-sidebar-foreground/70">Admin</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto">
        {ADMIN_NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="mb-2 px-2 text-[0.65rem] font-semibold uppercase tracking-wider text-sidebar-foreground/50">
              {section.label}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end ?? item.to === '/admin'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                          : 'text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                      )
                    }
                  >
                    <item.icon className="size-4 shrink-0 opacity-90" aria-hidden />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-sidebar-border pt-3">
        {me && me.authenticated ? (
          <NavLink
            to="/admin/profile"
            onClick={onNavigate}
            className="mb-2 block truncate rounded-md px-2 py-1 text-xs text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            title={me.username}
          >
            Signed in as <span className="font-medium">{me.username}</span>
          </NavLink>
        ) : null}
        <ThemeToggle />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-sidebar-foreground hover:bg-sidebar-accent"
          onClick={() => void handleLogout()}
        >
          <LogOut className="size-4 shrink-0" aria-hidden />
          Sign out
        </Button>
      </div>
    </div>
  )
}
