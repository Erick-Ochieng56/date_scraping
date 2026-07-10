export const notificationKeys = {
  all: ['notifications'] as const,
  list: (limit?: number) => ['notifications', 'list', limit ?? 'default'] as const,
}
