import type { ReactNode } from 'react'
import type { Item } from '../api'

export const btn = 'rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 '
export const btnPrimary = btn + 'bg-brick text-white hover:bg-brick-dark'
export const btnGhost = btn + 'border border-stone-300 dark:border-stone-700 hover:bg-stone-200 dark:hover:bg-stone-800'
export const input = 'w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900'

export function Err({ children }: { children: ReactNode }) {
  return children ? <p className="rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{children}</p> : null
}

export function Thumb({ item, className = '' }: { item: Item; className?: string }) {
  const src = item.set?.thumbnail_url || item.set?.image_url
  return src ? (
    <img src={src} alt="" loading="lazy" className={'bg-white object-contain ' + className} />
  ) : (
    <div className={'flex items-center justify-center bg-stone-200 text-3xl dark:bg-stone-800 ' + className}>🧱</div>
  )
}

export function TagList({ tags }: { tags: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map(t => (
        <a key={t} href={`#/?tag=${encodeURIComponent(t)}`}
           className="rounded-full bg-amber-200 px-2 py-0.5 text-xs text-amber-900 hover:bg-amber-300">{t}</a>
      ))}
    </div>
  )
}

/** Comma-separated tag editor with suggestions from existing tags. */
export function TagInput({ value, onChange, suggestions }: { value: string; onChange: (v: string) => void; suggestions: string[] }) {
  return (
    <>
      <input className={input} list="tag-suggestions" placeholder="tags, comma separated (e.g. childhood, display)"
             value={value} onChange={e => onChange(e.target.value)} />
      <datalist id="tag-suggestions">{suggestions.map(s => <option key={s} value={s} />)}</datalist>
    </>
  )
}
export const splitTags = (s: string) => s.split(',').map(t => t.trim()).filter(Boolean)
