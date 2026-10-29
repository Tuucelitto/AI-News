import type {
  ArticleDetail,
  ArticleListItem,
  ArticleQuery,
  Feed,
  FeedCreate,
  FeedRefreshResult,
  FeedUpdate,
  Page,
  QueueStatus,
} from '@/types/api'

/** An HTTP error from the API. `status` is 0 when the server could not be reached. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type QueryValue = string | number | boolean | null | undefined

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  query?: Record<string, QueryValue>
  body?: unknown
  adminKey?: string // required by every write endpoint (X-Admin-Key header)
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json()
    // FastAPI sends {"detail": "..."} for HTTPException and a list of errors for validation.
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) return data.detail.map((e: { msg: string }) => e.msg).join('; ')
  } catch {
    // Not JSON: fall through to the status text.
  }
  return response.statusText || `HTTP ${response.status}`
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, adminKey } = options

  const url = new URL(`/api${path}`, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    // Skip empty filters so the backend applies its defaults.
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (adminKey) headers['X-Admin-Key'] = adminKey

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Network error: the API could not be reached')
  }

  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  listArticles: (query: ArticleQuery = {}) =>
    request<Page<ArticleListItem>>('/articles', { query }),
  getArticle: (id: number) => request<ArticleDetail>(`/articles/${id}`),
  resummarizeArticle: (id: number, adminKey: string) =>
    request<ArticleDetail>(`/articles/${id}/resummarize`, { method: 'POST', adminKey }),

  listFeeds: () => request<Feed[]>('/feeds'),
  createFeed: (body: FeedCreate, adminKey: string) =>
    request<Feed>('/feeds', { method: 'POST', body, adminKey }),
  updateFeed: (id: number, body: FeedUpdate, adminKey: string) =>
    request<Feed>(`/feeds/${id}`, { method: 'PATCH', body, adminKey }),
  deleteFeed: (id: number, adminKey: string) =>
    request<void>(`/feeds/${id}`, { method: 'DELETE', adminKey }),
  refreshFeed: (id: number, adminKey: string) =>
    request<FeedRefreshResult>(`/feeds/${id}/refresh`, { method: 'POST', adminKey }),

  queueStatus: () => request<QueueStatus>('/queue/status'),
}
