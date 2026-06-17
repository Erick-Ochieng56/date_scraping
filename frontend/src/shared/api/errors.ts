import { isAxiosError } from 'axios'

export function getApiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (isAxiosError(err)) {
    const d = err.response?.data as { error?: string; detail?: string; message?: string } | undefined
    return d?.error ?? d?.detail ?? d?.message ?? err.message ?? fallback
  }
  if (err instanceof Error) return err.message
  return fallback
}
