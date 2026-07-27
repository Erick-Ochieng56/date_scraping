import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { passwordFormSchema, profileFormSchema, type PasswordFormValues, type ProfileFormValues } from '@/features/profile/schema'
import { getApiErrorMessage } from '@/shared/api/errors'
import { changePassword, getProfile, updateProfile } from '@/shared/api/profile'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'

function formatDateTime(value: string | null): string {
  if (!value) return 'Never'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString()
}

const ROLE_LABEL: Record<string, string> = { admin: 'Admin', staff: 'Staff' }

export function ProfilePage() {
  const qc = useQueryClient()
  const [profileBanner, setProfileBanner] = useState<{ message?: string; error?: string }>({})
  const [passwordBanner, setPasswordBanner] = useState<{ message?: string; error?: string }>({})

  const profileQ = useQuery({ queryKey: ['profile', 'me'], queryFn: getProfile })
  const profile = profileQ.data?.data

  const profileForm = useForm<ProfileFormValues>({
    defaultValues: { firstName: '', lastName: '', email: '' },
  })
  const passwordForm = useForm<PasswordFormValues>({
    defaultValues: { currentPassword: '', newPassword: '', confirmPassword: '' },
  })

  useEffect(() => {
    if (!profile) return
    profileForm.reset({
      firstName: profile.first_name,
      lastName: profile.last_name,
      email: profile.email,
    })
  }, [profile, profileForm])

  const updateM = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      updateProfile({
        first_name: values.firstName ?? '',
        last_name: values.lastName ?? '',
        email: values.email ?? '',
      }),
    onSuccess: (res) => {
      if (!res.success) {
        setProfileBanner({ error: res.error ?? 'Could not update profile.' })
        return
      }
      setProfileBanner({ message: 'Profile updated.' })
      void qc.invalidateQueries({ queryKey: ['profile', 'me'] })
    },
    onError: (err) => setProfileBanner({ error: getApiErrorMessage(err, 'Could not update profile.') }),
  })

  const passwordM = useMutation({
    mutationFn: (values: PasswordFormValues) =>
      changePassword({ current_password: values.currentPassword, new_password: values.newPassword }),
    onSuccess: (res) => {
      if (!res.success) {
        setPasswordBanner({ error: res.error ?? 'Could not change password.' })
        return
      }
      setPasswordBanner({ message: 'Password changed.' })
      passwordForm.reset({ currentPassword: '', newPassword: '', confirmPassword: '' })
    },
    onError: (err) => setPasswordBanner({ error: getApiErrorMessage(err, 'Could not change password.') }),
  })

  const onSubmitProfile = profileForm.handleSubmit((raw) => {
    setProfileBanner({})
    const parsed = profileFormSchema.safeParse(raw)
    if (!parsed.success) {
      setProfileBanner({ error: parsed.error.issues[0]?.message ?? 'Invalid form.' })
      return
    }
    updateM.mutate(parsed.data)
  })

  const onSubmitPassword = passwordForm.handleSubmit((raw) => {
    setPasswordBanner({})
    const parsed = passwordFormSchema.safeParse(raw)
    if (!parsed.success) {
      setPasswordBanner({ error: parsed.error.issues[0]?.message ?? 'Invalid form.' })
      return
    }
    passwordM.mutate(parsed.data)
  })

  return (
    <div className="space-y-6">
      <PageHeader title="My profile" description="View and update your own account details." />

      {profileQ.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {profileQ.isError ? (
        <AlertBanner error={getApiErrorMessage(profileQ.error, 'Failed to load your profile.')} />
      ) : null}

      {profile ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="font-semibold text-foreground">Account</h2>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Username</dt>
              <dd className="font-medium text-foreground">{profile.username}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Role</dt>
              <dd className="font-medium text-foreground">
                {profile.role ? (ROLE_LABEL[profile.role] ?? profile.role) : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Joined</dt>
              <dd className="font-medium text-foreground">{formatDateTime(profile.date_joined)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Last signed in</dt>
              <dd className="font-medium text-foreground">{formatDateTime(profile.last_login)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Username and role are managed by an administrator and can't be changed here.
          </p>
        </div>
      ) : null}

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-foreground">Edit profile</h2>
        <form className="mt-3 space-y-3" onSubmit={onSubmitProfile}>
          <AlertBanner message={profileBanner.message} error={profileBanner.error} />
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              label="First name"
              htmlFor="profile-first-name"
              error={profileForm.formState.errors.firstName?.message}
            >
              <Input id="profile-first-name" {...profileForm.register('firstName')} />
            </FormField>
            <FormField
              label="Last name"
              htmlFor="profile-last-name"
              error={profileForm.formState.errors.lastName?.message}
            >
              <Input id="profile-last-name" {...profileForm.register('lastName')} />
            </FormField>
          </div>
          <FormField label="Email" htmlFor="profile-email" error={profileForm.formState.errors.email?.message}>
            <Input id="profile-email" type="email" {...profileForm.register('email')} />
          </FormField>
          <Button type="submit" disabled={updateM.isPending || profileQ.isLoading}>
            {updateM.isPending ? 'Saving…' : 'Save changes'}
          </Button>
        </form>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-foreground">Change password</h2>
        <form className="mt-3 max-w-sm space-y-3" onSubmit={onSubmitPassword}>
          <AlertBanner message={passwordBanner.message} error={passwordBanner.error} />
          <FormField
            label="Current password"
            htmlFor="profile-current-password"
            error={passwordForm.formState.errors.currentPassword?.message}
          >
            <Input id="profile-current-password" type="password" autoComplete="current-password" {...passwordForm.register('currentPassword')} />
          </FormField>
          <FormField
            label="New password"
            htmlFor="profile-new-password"
            error={passwordForm.formState.errors.newPassword?.message}
            hint="At least 8 characters."
          >
            <Input id="profile-new-password" type="password" autoComplete="new-password" {...passwordForm.register('newPassword')} />
          </FormField>
          <FormField
            label="Confirm new password"
            htmlFor="profile-confirm-password"
            error={passwordForm.formState.errors.confirmPassword?.message}
          >
            <Input id="profile-confirm-password" type="password" autoComplete="new-password" {...passwordForm.register('confirmPassword')} />
          </FormField>
          <Button type="submit" variant="outline" disabled={passwordM.isPending}>
            {passwordM.isPending ? 'Updating…' : 'Change password'}
          </Button>
        </form>
      </div>
    </div>
  )
}
