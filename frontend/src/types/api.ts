// TypeScript mirrors of the backend response schemas (backend/app/schemas.py).
// Datetimes arrive as ISO 8601 strings in UTC, e.g. "2026-10-29T19:56:19Z".

export type SummaryStatus = 'new' | 'pending' | 'processing' | 'done' | 'skipped' | 'failed'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ArticleListItem {
  id: number
  feed_id: number
  feed_name: string
  title: string
  url: string
  published_at: string | null
  title_tr: string | null
  summary_tr: string | null
  rss_summary: string | null
  summary_status: SummaryStatus
}

export interface ArticleDetail extends ArticleListItem {
  author: string | null
  key_points: string[] | null
  model_used: string | null
  summarized_at: string | null
}

// A type alias (not an interface) so it can be passed where a plain record is expected.
export type ArticleQuery = {
  page?: number
  size?: number
  feed_id?: number
  status?: SummaryStatus
  q?: string
  since_hours?: number
}

export interface Feed {
  id: number
  name: string
  url: string
  site_url: string | null
  is_active: boolean
  last_fetched_at: string | null
  last_error: string | null
  article_count: number
}

export interface FeedCreate {
  url: string
  name?: string
}

export interface FeedUpdate {
  name?: string
  is_active?: boolean
}

export interface FeedRefreshResult {
  new_articles: number
  not_modified: boolean
  error: string | null
  queued_for_summary: number
  skipped: number
}

export interface ModelStatus {
  model: string
  role: 'primary' | 'fallback'
  requests_today: number
  daily_limit: number
  quota_resets_at: string
  paused_until: string | null
}

export interface QueueStatus {
  counts: Record<SummaryStatus, number>
  models: ModelStatus[]
  scheduler_running: boolean
  last_fetch_at: string | null
  next_fetch_at: string | null
}
