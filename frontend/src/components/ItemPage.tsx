import { useEffect, useState } from 'react'
import { api, type Item } from '../api'
import { btnGhost, btnPrimary, Err, input, splitTags, TagInput, Thumb } from './ui'

export default function ItemPage({ id }: { id: number }) {
  const [item, setItem] = useState<Item | null>(null)
  const [box, setBox] = useState(''); const [notes, setNotes] = useState(''); const [tags, setTags] = useState('')
  const [title, setTitle] = useState(''); const [desc, setDesc] = useState('')
  const [allTags, setAllTags] = useState<string[]>([]); const [boxes, setBoxes] = useState<string[]>([])
  const [err, setErr] = useState(''); const [saved, setSaved] = useState(false)

  const load = (i: Item) => {
    setItem(i); setBox(i.box); setNotes(i.notes); setTags(i.tags.join(', ')); setTitle(i.title); setDesc(i.description ?? '')
  }
  useEffect(() => {
    api.item(id).then(load).catch(e => setErr(e.message))
    api.facets().then(f => { setAllTags(f.tags.map(t => t.name)); setBoxes(f.boxes.map(b => b.name)) })
  }, [id])

  if (!item) return <Err>{err}</Err>
  const save = async () => {
    setErr(''); setSaved(false)
    try {
      load(await api.update(id, { box, notes, tags: splitTags(tags), ...(item.type === 'other' ? { title, description: desc } : {}) }))
      setSaved(true)
    } catch (e) { setErr((e as Error).message) }
  }
  const del = async () => {
    if (!confirm(`Delete “${item.title}” from your collection?`)) return
    await api.remove(id); window.location.hash = '#/'
  }
  const s = item.set
  return (
    <div className="mx-auto max-w-3xl">
      <a href="#/" className="text-sm text-stone-500 hover:underline">← Back</a>
      <div className="mt-3 grid gap-6 md:grid-cols-[16rem_1fr]">
        <Thumb item={item} className="h-64 w-full rounded-xl" />
        <div className="space-y-3">
          {item.type === 'other' ? (
            <>
              <input className={input + ' text-lg font-semibold'} value={title} onChange={e => setTitle(e.target.value)} />
              <textarea className={input} rows={2} placeholder="Description" value={desc} onChange={e => setDesc(e.target.value)} />
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold">{item.title}</h1>
              <p className="text-sm text-stone-500">
                {s?.number}-{s?.number_variant} · {s?.year} · {[s?.theme, s?.subtheme].filter(Boolean).join(' / ')}
                {s?.pieces ? ` · ${s.pieces} pieces` : ''}{s?.minifigs ? ` · ${s.minifigs} minifigs` : ''}
                {s?.brickset_url?.startsWith('https://brickset.com/') && <> · <a className="text-brick underline" href={s.brickset_url} target="_blank" rel="noreferrer">Brickset</a></>}
              </p>
            </>
          )}
          <label className="block text-sm font-medium">Box
            <input className={input + ' font-mono'} list="boxes" value={box} onChange={e => setBox(e.target.value)} placeholder="e.g. 587B" />
            <datalist id="boxes">{boxes.map(b => <option key={b} value={b} />)}</datalist>
          </label>
          <label className="block text-sm font-medium">Tags<TagInput value={tags} onChange={setTags} suggestions={allTags} /></label>
          <label className="block text-sm font-medium">Notes
            <textarea className={input} rows={4} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Missing pieces, condition, anything…" />
          </label>
          <Err>{err}</Err>
          <div className="flex items-center gap-2">
            <button className={btnPrimary} onClick={save}>Save</button>
            <button className={btnGhost} onClick={del}>Delete</button>
            {saved && <span className="text-sm text-green-600">Saved ✓</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
