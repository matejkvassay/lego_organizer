export type LegoSet = {
  set_id: number; number: string; number_variant: number; name: string
  year: number | null; theme: string | null; subtheme: string | null
  pieces: number | null; minifigs: number | null
  image_url: string | null; thumbnail_url: string | null; brickset_url: string | null
}
export type Item = {
  id: number; type: 'set' | 'other'; title: string; description: string | null
  box: string; notes: string; tags: string[]; set: LegoSet | null
}
export type Candidate = {
  set_id: number; number: string; name: string; year: number | null
  theme: string | null; image_url: string | null; reason: string
}
export type Facets = {
  total: number; others: number
  themes: { name: string; count: number; subthemes: { name: string; count: number }[] }[]
  tags: { name: string; count: number }[]
  boxes: { name: string; count: number }[]
}
export type Filters = { q?: string; theme?: string; subtheme?: string; tag?: string; box?: string; type?: string }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init)
  if (r.status === 401) { window.dispatchEvent(new Event('unauthorized')); throw new Error('Not signed in') }
  if (!r.ok) {
    let msg = r.statusText
    try { const b = await r.json(); msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail) } catch { /* keep statusText */ }
    throw new Error(msg)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}
const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})

export const api = {
  items: (f: Filters) => call<Item[]>('/api/items?' + new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][])),
  item: (id: number) => call<Item>(`/api/items/${id}`),
  facets: () => call<Facets>('/api/facets'),
  logout: () => call<void>('/auth/logout', { method: 'POST' }),
  create: (b: object) => call<Item>('/api/items', json('POST', b)),
  update: (id: number, b: object) => call<Item>(`/api/items/${id}`, json('PATCH', b)),
  remove: (id: number) => call<void>(`/api/items/${id}`, { method: 'DELETE' }),
  search: (query: string, mode: 'ai' | 'keyword') => call<Candidate[]>('/api/catalog/search', json('POST', { query, mode })),
  transcribe: (blob: Blob) => {
    const fd = new FormData(); fd.append('file', blob, 'speech.webm')
    return call<{ text: string }>('/api/transcribe', { method: 'POST', body: fd })
  },
}

export type Me = { email: string }
export const getMe = () => call<Me>('/auth/me')
