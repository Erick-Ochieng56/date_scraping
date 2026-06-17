export function fmtDate(v: string | null | undefined) {
  if (!v) return '—'
  return new Date(v).toLocaleString()
}

export type AdminBannerHandler = (message: string | null, error: string | null) => void
