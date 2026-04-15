import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { createStaffUser, listAdminUsers, transferOwnership, updateAdminUser, type AdminUser } from '@/lib/api/dashboard'

function fmtDate(v: string | null) {
  if (!v) return '—'
  return new Date(v).toLocaleString()
}

export function AdminUsersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [transferType, setTransferType] = useState<
    'scrape_targets' | 'scrape_runs' | 'crawl_runs' | 'crawl_sources' | 'crawl_domains' | 'prospects' | 'leads'
  >('scrape_targets')
  const [fromUserId, setFromUserId] = useState<number>(0)
  const [toUserId, setToUserId] = useState<number>(0)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const usersQ = useQuery({
    queryKey: ['admin-users', search],
    queryFn: () => listAdminUsers({ page_size: 100, search: search || undefined }),
  })

  const createM = useMutation({
    mutationFn: createStaffUser,
    onSuccess: () => {
      setMessage('Staff user created.')
      setError(null)
      setUsername('')
      setEmail('')
      setPassword('')
      void qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err: unknown) => {
      setMessage(null)
      const ax = err as { response?: { data?: { error?: string } } }
      setError(ax.response?.data?.error ?? 'Could not create staff user.')
    },
  })

  const updateM = useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: { role?: 'admin' | 'staff'; is_active?: boolean } }) =>
      updateAdminUser(userId, payload),
    onSuccess: () => {
      setMessage('User updated.')
      setError(null)
      void qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err: unknown) => {
      setMessage(null)
      const ax = err as { response?: { data?: { error?: string } } }
      setError(ax.response?.data?.error ?? 'Could not update user.')
    },
  })

  const transferM = useMutation({
    mutationFn: transferOwnership,
    onSuccess: (data) => {
      setMessage(`Ownership transfer completed. ${data.count} record(s) moved.`)
      setError(null)
      void qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (err: unknown) => {
      setMessage(null)
      const ax = err as { response?: { data?: { error?: string } } }
      setError(ax.response?.data?.error ?? 'Ownership transfer failed.')
    },
  })

  const rows = usersQ.data?.items ?? []

  const onCreate = () => {
    setMessage(null)
    setError(null)
    const u = username.trim()
    const p = password.trim()
    if (!u || !p) {
      setError('Username and password are required.')
      return
    }
    createM.mutate({ username: u, password: p, email: email.trim() || undefined })
  }

  const onTransfer = () => {
    setMessage(null)
    setError(null)
    if (!fromUserId || !toUserId) {
      setError('Select both source and destination users.')
      return
    }
    if (fromUserId === toUserId) {
      setError('Source and destination must be different users.')
      return
    }
    const fromUser = rows.find((r) => r.id === fromUserId)?.username ?? fromUserId
    const toUser = rows.find((r) => r.id === toUserId)?.username ?? toUserId
    const ok = window.confirm(`Transfer all ${transferType} records from ${fromUser} to ${toUser}?`)
    if (!ok) return
    transferM.mutate({
      object_type: transferType,
      from_user_id: fromUserId,
      to_user_id: toUserId,
      transfer_all: true,
    })
  }

  const toggleActive = (u: AdminUser) => {
    updateM.mutate({ userId: u.id, payload: { is_active: !u.is_active } })
  }

  const toggleRole = (u: AdminUser) => {
    const next = u.role === 'admin' ? 'staff' : 'admin'
    const ok = window.confirm(`Change ${u.username} to ${next.toUpperCase()} role?`)
    if (!ok) return
    updateM.mutate({ userId: u.id, payload: { role: next } })
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Users & roles</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Manage admin/staff access and create staff users directly from the UI.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/admin">Back to admin home</Link>
        </Button>
      </div>

      {(message || error) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {error ? <p className="text-destructive">{error}</p> : null}
          {message && !error ? <p>{message}</p> : null}
        </div>
      )}

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Create staff user</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Creates a React dashboard staff account (non-admin). Admin role can be granted later by superadmin.
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <input
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            placeholder="Email (optional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button disabled={createM.isPending} onClick={onCreate}>
            {createM.isPending ? 'Creating...' : 'Create staff user'}
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Ownership transfer</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Move all records of one type from one user to another (admin-only migration operation).
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={transferType}
            onChange={(e) => setTransferType(e.target.value as typeof transferType)}
          >
            <option value="scrape_targets">Scrape targets</option>
            <option value="scrape_runs">Scrape runs</option>
            <option value="crawl_runs">Crawl runs</option>
            <option value="crawl_sources">Crawl sources</option>
            <option value="crawl_domains">Crawl domains</option>
            <option value="prospects">Prospects</option>
            <option value="leads">Leads</option>
          </select>
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={fromUserId || ''}
            onChange={(e) => setFromUserId(Number(e.target.value))}
          >
            <option value="">From user...</option>
            {rows.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={toUserId || ''}
            onChange={(e) => setToUserId(Number(e.target.value))}
          >
            <option value="">To user...</option>
            {rows.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
          <Button disabled={transferM.isPending || rows.length === 0} onClick={onTransfer}>
            {transferM.isPending ? 'Transferring...' : 'Transfer ownership'}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          className="h-9 min-w-[260px] rounded-md border border-border bg-background px-3 text-sm"
          placeholder="Search username..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['admin-users'] })}>
          Refresh
        </Button>
      </div>

      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">User</th>
              <th className="px-3 py-2 text-left">Role</th>
              <th className="px-3 py-2 text-left">Active</th>
              <th className="px-3 py-2 text-left">Last login</th>
              <th className="px-3 py-2 text-left">Created</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <div className="font-medium">{u.username}</div>
                  <div className="text-xs text-muted-foreground">{u.email || '—'}</div>
                </td>
                <td className="px-3 py-2">{u.role.toUpperCase()}</td>
                <td className="px-3 py-2">{u.is_active ? 'Yes' : 'No'}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(u.last_login)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(u.date_joined)}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={updateM.isPending} onClick={() => toggleActive(u)}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button size="sm" variant="outline" disabled={updateM.isPending} onClick={() => toggleRole(u)}>
                      Make {u.role === 'admin' ? 'staff' : 'admin'}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {usersQ.isLoading ? <p className="text-sm text-muted-foreground">Loading users...</p> : null}
    </div>
  )
}
