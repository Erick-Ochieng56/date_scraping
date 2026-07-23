import { Moon, Sun } from 'lucide-react'

import { useTheme } from '@/shared/hooks/useTheme'
import { cn } from '@/lib/utils'

/** Compact light/dark switch for the sidebar footer. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={cn(
        'inline-flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm font-medium',
        'text-sidebar-foreground/90 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
        className
      )}
    >
      {isDark ? <Sun className="size-4 shrink-0" aria-hidden /> : <Moon className="size-4 shrink-0" aria-hidden />}
      {isDark ? 'Light mode' : 'Dark mode'}
    </button>
  )
}
