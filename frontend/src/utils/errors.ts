import { ApiError } from '@/api/client'

// Known backend messages (English, from FastAPI) shown to the reader in Turkish.
const DETAILS: Record<string, string> = {
  'A feed with this URL already exists': 'Bu adresle bir kaynak zaten var.',
  'URL is not a valid RSS/Atom feed': 'Bu adres geçerli bir RSS/Atom kaynağı değil.',
  'Feed not found': 'Kaynak bulunamadı.',
  'Article not found': 'Haber bulunamadı.',
}

/** A Turkish, user-facing message for any error thrown by the API client. */
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error)

  switch (error.status) {
    case 0:
      return 'Sunucuya ulaşılamadı. Backend çalışıyor mu?'
    case 401:
      return 'Yönetici anahtarı yanlış.'
    case 403:
      return 'Sunucuda yazma işlemleri kapalı (ADMIN_API_KEY ayarlı değil).'
  }
  if (error.message in DETAILS) return DETAILS[error.message]!
  if (error.message.startsWith('Could not download feed')) {
    return `Kaynak indirilemedi (${error.message.split(': ').pop()}).`
  }
  if (error.status === 409 && error.message.startsWith('Article is')) {
    return 'Bu haber zaten özet kuyruğunda.'
  }
  return error.message
}
