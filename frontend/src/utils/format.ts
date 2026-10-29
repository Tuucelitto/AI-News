// Date formatting with the browser's built-in Intl API (no date library needed).

const relativeFormat = new Intl.RelativeTimeFormat('tr', { numeric: 'auto' })

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

/** "3 saat önce", "dün", "az önce". `now` is a parameter so tests can fix the time. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) {
      // trunc, not round: 90 minutes ago reads better as "1 saat önce" than "2 saat önce".
      return relativeFormat.format(Math.trunc(seconds / size), unit)
    }
  }
  return 'az önce'
}

/** "29 Ekim 2026 22:56" in the viewer's time zone (or the given one, for tests). */
export function formatDate(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('tr-TR', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(iso))
}
