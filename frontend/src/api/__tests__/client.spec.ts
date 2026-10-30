import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '@/api/client'

// Typed like the real fetch, so the mock cannot be used in ways fetch would not allow.
const fetchMock = vi.fn<typeof fetch>()

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function lastCall(): { url: URL; init: RequestInit } {
  const [url, init] = fetchMock.mock.lastCall!
  return { url: url as URL, init: init ?? {} }
}

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock) // tests never hit a real server
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  it('builds the query string and skips empty filters', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], total: 0, page: 2, size: 20 }))

    await api.listArticles({ page: 2, since_hours: 24, q: '', feed_id: undefined })

    const { url, init } = lastCall()
    expect(url.pathname).toBe('/api/articles')
    expect(url.search).toBe('?page=2&since_hours=24')
    expect(init.method).toBe('GET')
  })

  it('sends the admin key and a JSON body on writes', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1 }, 201))

    await api.createFeed({ url: 'https://example.com/rss' }, 'secret')

    const { url, init } = lastCall()
    expect(url.pathname).toBe('/api/feeds')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json', 'X-Admin-Key': 'secret' })
    expect(init.body).toBe('{"url":"https://example.com/rss"}')
  })

  it('does not send an admin key on reads', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]))

    await api.listFeeds()

    expect(lastCall().init.headers).toEqual({})
  })

  it('throws ApiError with the backend detail message', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Feed not found' }, 404))

    const error = await api.deleteFeed(9, 'secret').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, message: 'Feed not found' })
  })

  it('joins validation error messages', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: [{ msg: 'Input should be a valid URL' }, { msg: 'Too long' }] }, 422),
    )

    await expect(api.createFeed({ url: 'x' }, 'secret')).rejects.toMatchObject({
      status: 422,
      message: 'Input should be a valid URL; Too long',
    })
  })

  it('returns undefined for 204 No Content', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))

    await expect(api.deleteFeed(1, 'secret')).resolves.toBeUndefined()
  })

  it('turns network failures into ApiError with status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(api.queueStatus('key')).rejects.toMatchObject({ name: 'ApiError', status: 0 })
  })
})
