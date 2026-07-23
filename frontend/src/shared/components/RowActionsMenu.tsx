import { DropdownMenu } from 'radix-ui'
import { MoreHorizontal } from 'lucide-react'

import { cn } from '@/lib/utils'

export type RowAction = {
  label: string
  onSelect: () => void
  disabled?: boolean
  /** Destructive actions get the red treatment; everything else stays neutral. */
  destructive?: boolean
}

/**
 * Kebab (⋯) overflow menu for secondary row actions, so a row shows one primary
 * button (usually "View") instead of stacking every action inline.
 * (UI_REDESIGN_PLAN.md Phase 1 — Prospects/Leads rows had 4 buttons each.)
 */
export function RowActionsMenu({ label, actions }: { label: string; actions: RowAction[] }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <MoreHorizontal className="size-4" aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[10rem] rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {actions.map((action) => (
            <DropdownMenu.Item
              key={action.label}
              disabled={action.disabled}
              onSelect={action.onSelect}
              className={cn(
                'flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors',
                'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                action.destructive
                  ? 'text-destructive data-[highlighted]:bg-destructive/10'
                  : 'text-foreground data-[highlighted]:bg-muted'
              )}
            >
              {action.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
