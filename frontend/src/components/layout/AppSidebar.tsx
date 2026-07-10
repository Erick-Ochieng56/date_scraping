import { LogOut } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { NAV_SECTIONS } from '@/app/navigation'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
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
        <img src="/atericlogo.svg" alt="" className="size-9 shrink-0 rounded-md bg-muted p-1" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-sidebar-foreground">Ateric</p>
          <p className="truncate text-xs text-muted-foreground">Scraper portal</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="mb-2 px-2 text-xs font-medium tracking-wide text-muted-foreground">
              {section.label}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                        isActive
                          ? 'bg-sidebar-accent font-bold text-sidebar-foreground'
                          : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground'
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

      <div className="border-t border-sidebar-border pt-3">
        {me && me.authenticated && me.role === 'staff' ? (
          <p className="mb-2 truncate px-2 text-xs text-sidebar-foreground/80">
            Signed in as{' '}
            <Link
              to="/profile"
              className="font-medium text-sidebar-foreground underline-offset-2 hover:underline"
              title={me.username}
              onClick={onNavigate}
            >
              {me.username}
            </Link>
          </p>
        ) : null}
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
        <p className="mt-3 px-2 text-xs text-muted-foreground">
          API:{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.65rem]">
            {import.meta.env.VITE_API_BASE || '(proxy → :8000)'}
          </code>
        </p>
      </div>
    </div>
  )
}
