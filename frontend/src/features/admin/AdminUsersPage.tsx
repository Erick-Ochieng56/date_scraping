import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { fmtDate } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  createStaffUser,
  listAdminUsers,
  transferOwnership,
  updateAdminUser,
} from '@/shared/api/admin'
import type { AdminUser } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue'
import { useServerList } from '@/shared/hooks/useServerList'

export function AdminUsersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [transferType, setTransferType] = useState<
    'scrape_targets' | 'scrape_runs' | 'crawl_runs' | 'crawl_sources' | 'crawl_domains' | 'prospects' | 'leads'
  >('scrape_targets')
  const [fromUserId, setFromUserId] = useState<number>(0)
  const [toUserId, setToUserId] = useState<number>(0)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const { items, total, page, hasNext, goNext, goPrev, query } = useServerList<AdminUser>({
    queryKey: ['admin', 'users'],
    queryFn: listAdminUsers,
    pageSize: 50,
    search: debouncedSearch,
  })

  const createM = useMutation({
    mutationFn: createStaffUser,
    onSuccess: () => {
      setBanner({ message: 'Staff user created.' })
      setUsername('')
      setEmail('')
      setPassword('')
      void qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const updateM = useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: { role?: 'admin' | 'staff'; is_active?: boolean } }) =>
      updateAdminUser(userId, payload),
    onSuccess: () => {
      setBanner({ message: 'User updated.' })
      void qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const transferM = useMutation({
    mutationFn: transferOwnership,
    onSuccess: (data) => {
      setBanner({ message: `Ownership transfer completed. ${data.count} record(s) moved.` })
      void qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const onCreate = () => {
    setBanner({})
    const u = username.trim()
    const p = password.trim()
    if (!u || !p) {
      setBanner({ error: 'Username and password are required.' })
      return
    }
    createM.mutate({ username: u, password: p, email: email.trim() || undefined })
  }

  const onTransfer = () => {
    setBanner({})
    if (!fromUserId || !toUserId) {
      setBanner({ error: 'Select both source and destination users.' })
      return
    }
    if (fromUserId === toUserId) {
      setBanner({ error: 'Source and destination must be different users.' })
      return
    }
    const fromUser = items.find((r) => r.id === fromUserId)?.username ?? fromUserId
    const toUser = items.find((r) => r.id === toUserId)?.username ?? toUserId
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

  const columns = useMemo<ColumnDef<AdminUser, unknown>[]>(
    () => [
      {
        accessorKey: 'username',
        header: 'User',
        cell: ({ row }) => (
          <div>
            <div className="font-medium">{row.original.username}</div>
            <div className="text-xs text-muted-foreground">{row.original.email || '—'}</div>
          </div>
        ),
      },
      {
        accessorKey: 'role',
        header: 'Role',
        cell: ({ row }) => row.original.role.toUpperCase(),
      },
      {
        accessorKey: 'is_active',
        header: 'Active',
        cell: ({ row }) => (row.original.is_active ? 'Yes' : 'No'),
      },
      {
        accessorKey: 'last_login',
        header: 'Last login',
        cell: ({ row }) => fmtDate(row.original.last_login),
      },
      {
        accessorKey: 'date_joined',
        header: 'Created',
        cell: ({ row }) => fmtDate(row.original.date_joined),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" disabled={updateM.isPending} onClick={() => toggleActive(row.original)}>
              {row.original.is_active ? 'Deactivate' : 'Activate'}
            </Button>
            <Button size="sm" variant="outline" disabled={updateM.isPending} onClick={() => toggleRole(row.original)}>
              Make {row.original.role === 'admin' ? 'staff' : 'admin'}
            </Button>
          </div>
        ),
      },
    ],
    [updateM.isPending]
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Users & roles"
        description="Manage admin/staff access and create staff users directly from the UI."
        actions={
          <Button variant="outline" asChild>
            <Link to="/admin">Back to admin home</Link>
          </Button>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Create staff user</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Creates a React dashboard staff account (non-admin). Admin role can be granted later by superadmin.
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <Input placeholder="Email (optional)" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button disabled={createM.isPending} onClick={onCreate}>
            {createM.isPending ? 'Creating…' : 'Create staff user'}
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Ownership transfer</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Move all records of one type from one user to another (admin-only migration operation).
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <Select value={transferType} onChange={(e) => setTransferType(e.target.value as typeof transferType)}>
            <option value="scrape_targets">Scrape targets</option>
            <option value="scrape_runs">Scrape runs</option>
            <option value="crawl_runs">Crawl runs</option>
            <option value="crawl_sources">Crawl sources</option>
            <option value="crawl_domains">Crawl domains</option>
            <option value="prospects">Prospects</option>
            <option value="leads">Leads</option>
          </Select>
          <Select value={fromUserId || ''} onChange={(e) => setFromUserId(Number(e.target.value))}>
            <option value="">From user…</option>
            {items.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </Select>
          <Select value={toUserId || ''} onChange={(e) => setToUserId(Number(e.target.value))}>
            <option value="">To user…</option>
            {items.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </Select>
          <Button disabled={transferM.isPending || items.length === 0} onClick={onTransfer}>
            {transferM.isPending ? 'Transferring…' : 'Transfer ownership'}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[260px] flex-1"
          placeholder="Search username…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button variant="outline" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load users.') : null}
        emptyMessage="No users match your search."
        getRowId={(r) => String(r.id)}
      />

      <p className="text-sm text-muted-foreground">
        {total} user{total === 1 ? '' : 's'} · page {page}
      </p>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={goPrev}>
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={!hasNext} onClick={goNext}>
          Next
        </Button>
      </div>
    </div>
  )
}
