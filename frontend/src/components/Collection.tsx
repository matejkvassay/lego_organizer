import { useEffect, useState } from 'react'
import { api, type Facets, type Filters, type Item } from '../api'
import { href } from '../route'
import { btnGhost, Err, TagList, Thumb } from './ui'

function Sidebar({ facets, f }: { facets: Facets | null; f: Filters }) {
  if (!facets) return <aside className="w-60 shrink-0" />
  const link = (label: string, count: number, to: Filters, active: boolean, indent = false) => (
    <a key={label + JSON.stringify(to)} href={href(to)}
       className={`flex justify-between rounded px-2 py-1 text-sm hover:bg-stone-200 dark:hover:bg-stone-800 ${indent ? 'ml-4' : ''} ${active ? 'bg-stone-200 font-semibold dark:bg-stone-800' : ''}`}>
      <span className="truncate">{label}</span><span className="text-stone-500">{count}</span>
    </a>
  )
  const h = 'mb-1 mt-4 px-2 text-xs font-semibold uppercase tracking-wide text-stone-500'
  return (
    <aside className="w-60 shrink-0">
      {link('Everything', facets.total, {}, !f.theme && !f.tag && !f.box && !f.type)}
      <h3 className={h}>Themes</h3>
      {facets.themes.map(t => (
        <div key={t.name}>
          {link(t.name, t.count, { theme: t.name }, f.theme === t.name && !f.subtheme)}
          {f.theme === t.name && t.subthemes.map(s => link(s.name, s.count, { theme: t.name, subtheme: s.name }, f.subtheme === s.name, true))}
        </div>
      ))}
      {facets.others > 0 && <><h3 className={h}>Other</h3>{link('Non-set items', facets.others, { type: 'other' }, f.type === 'other')}</>}
      {facets.tags.length > 0 && <h3 className={h}>Tags</h3>}
      {facets.tags.map(t => link(t.name, t.count, { tag: t.name }, f.tag === t.name))}
      {facets.boxes.length > 0 && <h3 className={h}>Boxes</h3>}
      {facets.boxes.map(b => link(b.name, b.count, { box: b.name }, f.box === b.name))}
    </aside>
  )
}

export default function Collection({ filters }: { filters: Filters }) {
  const [items, setItems] = useState<Item[] | null>(null)
  const [facets, setFacets] = useState<Facets | null>(null)
  const [err, setErr] = useState('')
  const [view, setView] = useState<'grid' | 'table'>(() => (localStorage.getItem('view') as 'grid' | 'table') || 'grid')
  const key = JSON.stringify(filters)

  useEffect(() => { api.facets().then(setFacets).catch(e => setErr(e.message)) }, [])
  useEffect(() => {
    setItems(null)
    api.items(filters).then(setItems).catch(e => setErr(e.message))
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const setV = (v: 'grid' | 'table') => { setView(v); localStorage.setItem('view', v) }
  const crumbs = [filters.q && `search “${filters.q}”`, filters.theme, filters.subtheme, filters.tag && `#${filters.tag}`,
    filters.box && `box ${filters.box}`, filters.type === 'other' && 'other items'].filter(Boolean).join(' › ')

  return (
    <div className="flex gap-6">
      <Sidebar facets={facets} f={filters} />
      <section className="min-w-0 flex-1">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{crumbs || 'Everything'} <span className="text-sm font-normal text-stone-500">{items ? `(${items.length})` : ''}</span></h2>
          <div className="flex gap-1">
            <button className={btnGhost} onClick={() => setV(view === 'grid' ? 'table' : 'grid')}>{view === 'grid' ? 'Table view' : 'Grid view'}</button>
          </div>
        </div>
        <Err>{err}</Err>
        {items && items.length === 0 && (
          <p className="py-16 text-center text-stone-500">Nothing here yet. <a className="text-brick underline" href="#/add">Add a set</a>.</p>
        )}
        {items && view === 'grid' && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            {items.map(i => (
              <a key={i.id} href={`#/item/${i.id}`} className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-stone-200 transition hover:shadow-md dark:bg-stone-900 dark:ring-stone-800">
                <Thumb item={i} className="h-36 w-full" />
                <div className="space-y-1 p-3">
                  <div className="line-clamp-2 text-sm font-medium">{i.title}</div>
                  <div className="text-xs text-stone-500">{i.set ? `${i.set.number} · ${i.set.year ?? ''}` : 'other'}</div>
                  <div className="text-xs">📦 {i.box || <span className="text-stone-400">no box</span>}</div>
                </div>
              </a>
            ))}
          </div>
        )}
        {items && view === 'table' && items.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-stone-500"><tr>
              <th className="p-2" /><th className="p-2">Name</th><th className="p-2">No.</th><th className="p-2">Theme</th>
              <th className="p-2">Year</th><th className="p-2">Box</th><th className="p-2">Tags</th></tr></thead>
            <tbody>
              {items.map(i => (
                <tr key={i.id} className="border-t border-stone-200 hover:bg-stone-200/50 dark:border-stone-800 dark:hover:bg-stone-800/50">
                  <td className="w-12 p-1"><Thumb item={i} className="h-10 w-10 rounded" /></td>
                  <td className="p-2"><a className="font-medium hover:underline" href={`#/item/${i.id}`}>{i.title}</a></td>
                  <td className="p-2">{i.set?.number}</td>
                  <td className="p-2">{i.set ? [i.set.theme, i.set.subtheme].filter(Boolean).join(' / ') : 'other'}</td>
                  <td className="p-2">{i.set?.year}</td>
                  <td className="p-2 font-mono">{i.box}</td>
                  <td className="p-2"><TagList tags={i.tags} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
