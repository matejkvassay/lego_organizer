import { useEffect, useState } from 'react'
import type { Filters } from './api'

// Tiny hash router: #/  #/?theme=Star+Wars  #/add  #/item/12
export type Route = { page: 'home' | 'add' | 'item'; id?: number; filters: Filters }

export function parse(hash: string): Route {
  const [path, qs = ''] = hash.replace(/^#/, '').split('?')
  const p = new URLSearchParams(qs)
  const filters: Filters = {}
  for (const k of ['q', 'theme', 'subtheme', 'tag', 'box', 'type'] as const) if (p.get(k)) filters[k] = p.get(k)!
  if (path.startsWith('/add')) return { page: 'add', filters }
  const m = path.match(/^\/item\/(\d+)/)
  if (m) return { page: 'item', id: Number(m[1]), filters }
  return { page: 'home', filters }
}

export const href = (f: Filters = {}) => {
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString()
  return '#/' + (qs ? '?' + qs : '')
}

export function useRoute(): Route {
  const [r, setR] = useState(() => parse(window.location.hash))
  useEffect(() => {
    const on = () => setR(parse(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return r
}
