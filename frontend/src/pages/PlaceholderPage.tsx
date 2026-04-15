import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

type PlaceholderPageProps = {
  title: string
  description?: string
  /** Path on the Django admin (template) dashboard, e.g. `/dashboard/targets/` */
  adminTemplatePath?: string
}

export function PlaceholderPage({ title, description, adminTemplatePath }: PlaceholderPageProps) {
  const djangoBase = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
  const href = adminTemplatePath ? `${djangoBase.replace(/\/$/, '')}${adminTemplatePath}` : undefined

  return (
    <div className="mx-auto max-w-2xl rounded-xl border border-border bg-card p-8 shadow-sm">
      <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
      {description ? (
        <p className="mt-2 text-muted-foreground">{description}</p>
      ) : (
        <p className="mt-2 text-muted-foreground">
          React UI for staff — full lists will use the API here. Admins can use the template dashboard for the same data
          paths today.
        </p>
      )}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="secondary" asChild>
          <Link to="/">Back to dashboard</Link>
        </Button>
        {href ? (
          <Button variant="outline" asChild>
            <a href={href} target="_blank" rel="noreferrer">
              Open in admin dashboard (Django)
            </a>
          </Button>
        ) : null}
      </div>
    </div>
  )
}
