import { describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import { errorMessage } from '@/utils/errors'

describe('errorMessage', () => {
  it.each([
    [new ApiError(0, 'Network error'), 'Sunucuya ulaşılamadı. Backend çalışıyor mu?'],
    [new ApiError(401, 'Invalid or missing X-Admin-Key header'), 'Yönetici anahtarı yanlış.'],
    [new ApiError(409, 'A feed with this URL already exists'), 'Bu adresle bir kaynak zaten var.'],
    [new ApiError(422, 'Could not download feed: HTTP 404'), 'Kaynak indirilemedi (HTTP 404).'],
    [new ApiError(409, 'Article is pending, not finished'), 'Bu haber zaten özet kuyruğunda.'],
    [new ApiError(500, 'Something unexpected'), 'Something unexpected'],
    [new Error('boom'), 'boom'],
  ])('%s → %s', (error, expected) => {
    expect(errorMessage(error)).toBe(expected)
  })
})
