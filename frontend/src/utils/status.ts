import type { SummaryStatus } from '@/types/api'

export interface StatusInfo {
  label: string
  description: string
  tone: 'waiting' | 'muted' | 'error'
}

/** How a summary status is shown to the reader. `null` for "done": nothing to point out. */
export function statusInfo(status: SummaryStatus): StatusInfo | null {
  switch (status) {
    case 'done':
      return null
    case 'new':
    case 'pending':
    case 'processing':
      return {
        label: 'Özet hazırlanıyor',
        description: 'Türkçe özet birkaç dakika içinde hazır olacak. Şimdilik orijinal açıklama:',
        tone: 'waiting',
      }
    case 'skipped':
      return {
        label: 'Özet yok',
        description: 'Bu haber özetlenemeyecek kadar kısa. Orijinal açıklama:',
        tone: 'muted',
      }
    case 'failed':
      return {
        label: 'Özetlenemedi',
        description: 'Bu haber için Türkçe özet oluşturulamadı. Orijinal açıklama:',
        tone: 'error',
      }
  }
}
