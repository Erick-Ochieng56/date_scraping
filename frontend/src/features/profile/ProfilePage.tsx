import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { fmtDate } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { changePassword, fetchProfile, updateProfile } from '@/shared/api/profile'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DetailField } from '@/shared/components/DetailField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'

export const profileKeys = {
  all: ['profile'] as const,
  detail: () => [...profileKeys.all, 'detail'] as const,
}

type ProfilePageProps = {
  /** Base path for this portal (`/` staff or `/admin`). */
  homePath?: string
}

export function ProfilePage({ homePath = '/' }: ProfilePageProps) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const profileQ = useQuery({
    queryKey: profileKeys.detail(),
    queryFn: fetchProfile,
  })

  useEffect(() => {
    if (profileQ.data?.email != null) {
      setEmail(profileQ.data.email)
    }
  }, [profileQ.data?.email])

  const updateM = useMutation({
    mutationFn: () => updateProfile({ email: email.trim() }),
    onSuccess: (data) => {
      setBanner({ message: 'Profile updated.' })
      setEmail(data.email)
      void qc.invalidateQueries({ queryKey: profileKeys.all })
      void qc.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const passwordM = useMutation({
    mutationFn: () =>
      changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: () => {
      setBanner({ message: 'Password updated.' })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const profile = profileQ.data
  const emailDirty = profile != null && email.trim() !== profile.email

  const onSaveEmail = () => {
    setBanner({})
    if (!email.trim()) {
      setBanner({ error: 'Email cannot be empty.' })
      return
    }
    updateM.mutate()
  }

  const onChangePassword = () => {
    setBanner({})
    if (!currentPassword || !newPassword) {
      setBanner({ error: 'Enter your current and new password.' })
      return
    }
    if (newPassword !== confirmPassword) {
      setBanner({ error: 'New passwords do not match.' })
      return
    }
    passwordM.mutate()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Your profile"
        description="View account details and update your contact email or password."
        actions={
          <Button variant="outline" asChild>
            <Link to={homePath}>Back to home</Link>
          </Button>
        }
      />

      {banner.message || banner.error ? (
        <AlertBanner message={banner.message} error={banner.error} />
      ) : null}
      {profileQ.isError ? (
        <AlertBanner error="Could not load profile. Try refreshing the page." />
      ) : null}

      <section className="space-y-3">
        <SectionEyebrow>Account</SectionEyebrow>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <DetailField label="Username">{profile?.username ?? '—'}</DetailField>
          <DetailField label="Role">
            {profile?.role === 'admin' ? 'Administrator' : profile?.role === 'staff' ? 'Staff' : '—'}
            {profile?.is_superuser ? ' (superuser)' : null}
          </DetailField>
          <DetailField label="Member since">{fmtDate(profile?.date_joined)}</DetailField>
          <DetailField label="Last sign-in">{fmtDate(profile?.last_login)}</DetailField>
        </div>
      </section>

      <section className="space-y-3">
        <SectionEyebrow>Contact email</SectionEyebrow>
        <div className="max-w-md space-y-3 rounded-lg border border-border bg-card p-4">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-foreground">Email</span>
            <Input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={profileQ.isLoading || updateM.isPending}
            />
          </label>
          <Button type="button" onClick={onSaveEmail} disabled={!emailDirty || updateM.isPending}>
            {updateM.isPending ? 'Saving…' : 'Save email'}
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <SectionEyebrow>Change password</SectionEyebrow>
        <div className="max-w-md space-y-3 rounded-lg border border-border bg-card p-4">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-foreground">Current password</span>
            <Input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              disabled={passwordM.isPending}
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-foreground">New password</span>
            <Input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={passwordM.isPending}
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-foreground">Confirm new password</span>
            <Input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={passwordM.isPending}
            />
          </label>
          <Button type="button" variant="outline" onClick={onChangePassword} disabled={passwordM.isPending}>
            {passwordM.isPending ? 'Updating…' : 'Update password'}
          </Button>
        </div>
      </section>
    </div>
  )
}
