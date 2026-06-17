import { z } from 'zod'

export const aiSearchFormSchema = z.object({
  seedTopic: z.string().trim().min(1, 'Enter a seed topic.'),
  industry: z.string().optional(),
  region: z.string().optional(),
  delegateOwnerId: z.string().optional(),
})

export type AiSearchFormValues = z.infer<typeof aiSearchFormSchema>
