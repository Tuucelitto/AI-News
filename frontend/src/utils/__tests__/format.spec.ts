import { describe, expect, it } from 'vitest'

import { formatDate, formatRelative } from '@/utils/format'

const NOW = new Date('2026-10-30T12:00:00Z')

describe('formatRelative', () => {
  it.each([
    ['2026-10-30T11:59:30Z', 'az önce'],
    ['2026-10-30T11:55:00Z', '5 dakika önce'],
    ['2026-10-30T10:30:00Z', '1 saat önce'], // 90 minutes: truncated, not rounded up
    ['2026-10-29T12:00:00Z', 'dün'],
    ['2026-10-27T12:00:00Z', '3 gün önce'],
    ['2026-10-16T12:00:00Z', '2 hafta önce'],
  ])('%s → %s', (iso, expected) => {
    expect(formatRelative(iso, NOW)).toBe(expected)
  })
})

describe('formatDate', () => {
  it('formats in Turkish for the given time zone', () => {
    expect(formatDate('2026-10-29T19:56:00Z', 'Europe/Istanbul')).toBe('29 Ekim 2026 22:56')
  })
})
