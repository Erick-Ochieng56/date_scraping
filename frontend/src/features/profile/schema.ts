import { z } from 'zod'

export const profileFormSchema = z.object({
  firstName: z.string().trim().max(150).optional(),
  lastName: z.string().trim().max(150).optional(),
  email: z
    .string()
    .trim()
    .max(254)
    .optional()
    .refine((v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), 'Enter a valid email address.'),
})

export type ProfileFormValues = z.infer<typeof profileFormSchema>

export const passwordFormSchema = z
  .object({
    currentPassword: z.string().min(1, 'Enter your current password.'),
    newPassword: z.string().min(8, 'New password must be at least 8 characters.'),
    confirmPassword: z.string().min(1, 'Confirm your new password.'),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'New passwords do not match.',
    path: ['confirmPassword'],
  })

export type PasswordFormValues = z.infer<typeof passwordFormSchema>
