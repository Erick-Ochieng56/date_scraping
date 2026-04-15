import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react'
import { Menu, X } from 'lucide-react'
import { Suspense, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { AppSidebar } from '@/components/layout/AppSidebar'
import { PageContentSkeleton } from '@/components/PageContentSkeleton'
import { Button } from '@/components/ui/button'

export function DashboardLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
        <AppSidebar />
      </aside>

      {/* Mobile drawer */}
      <Dialog open={mobileOpen} onClose={setMobileOpen} className="relative z-50 md:hidden">
        <DialogBackdrop className="fixed inset-0 bg-black/40" transition />
        <div className="fixed inset-0 flex justify-start">
          <DialogPanel
            transition
            className="flex h-full w-[min(18rem,100%)] flex-col bg-sidebar shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-sidebar-border px-3 py-3">
              <DialogTitle className="text-sm font-semibold text-sidebar-foreground">Menu</DialogTitle>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="text-sidebar-foreground"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
              >
                <X className="size-5" />
              </Button>
            </div>
            <AppSidebar onNavigate={() => setMobileOpen(false)} />
          </DialogPanel>
        </div>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-card/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-card/80 md:px-6">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </Button>
          <h1 className="text-lg font-semibold text-foreground">Scraper dashboard</h1>
        </header>

        <main className="flex-1 p-4 md:p-6">
          <Suspense fallback={<PageContentSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
