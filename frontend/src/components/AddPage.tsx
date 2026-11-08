import { useEffect, useRef, useState } from 'react'
import { api, type Candidate } from '../api'
import { btnGhost, btnPrimary, Err, input, splitTags, TagInput } from './ui'

function useRecorder(onText: (t: string) => void, onError: (m: string) => void) {
  const [state, setState] = useState<'idle' | 'recording' | 'working'>('idle')
  const rec = useRef<MediaRecorder | null>(null)
  const toggle = async () => {
    if (state === 'recording') { rec.current?.stop(); return }
    if (state !== 'idle') return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks: Blob[] = []
      const r = new MediaRecorder(stream)
      r.ondataavailable = e => chunks.push(e.data)
      r.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        setState('working')
        try { onText((await api.transcribe(new Blob(chunks, { type: r.mimeType }))).text) }
        catch (e) { onError((e as Error).message) }
        setState('idle')
      }
      r.start(); rec.current = r; setState('recording')
    } catch { onError('Microphone not available (check browser permission).') }
  }
  return { state, toggle }
}

function AddSet() {
  const [mode, setMode] = useState<'ai' | 'keyword'>('ai')
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Candidate[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [picked, setPicked] = useState<Candidate | null>(null)
  const [box, setBox] = useState(''); const [tags, setTags] = useState(''); const [notes, setNotes] = useState('')
  const [allTags, setAllTags] = useState<string[]>([]); const [boxes, setBoxes] = useState<string[]>([])
  const [added, setAdded] = useState<string[]>([])
  const mic = useRecorder(t => setQ(t), setErr)

  useEffect(() => { api.facets().then(f => { setAllTags(f.tags.map(t => t.name)); setBoxes(f.boxes.map(b => b.name)) }) }, [added])

  const run = async () => {
    if (!q.trim()) return
    setBusy(true); setErr(''); setPicked(null); setResults(null)
    try { setResults(await api.search(q, mode)) } catch (e) { setErr((e as Error).message) }
    setBusy(false)
  }
  const save = async () => {
    if (!picked) return
    setErr('')
    try {
      await api.create({ type: 'set', brickset_set_id: picked.set_id, box, tags: splitTags(tags), notes })
      setAdded(a => [`${picked.number} ${picked.name} → ${box || 'no box'}`, ...a])
      setPicked(null); setResults(null); setQ(''); setNotes('')  // keep box + tags: you usually add several sets to one box
    } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input className={input} autoFocus value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()}
               placeholder={mode === 'ai' ? 'Describe it: “the pharaoh castle from adventurers”…' : 'Keywords or set number'} />
        <button className={btnGhost + (mic.state === 'recording' ? ' !bg-red-600 !text-white' : '')} onClick={mic.toggle} title="Speak">
          {mic.state === 'recording' ? '■ Stop' : mic.state === 'working' ? '…' : '🎤'}
        </button>
        <button className={btnPrimary} onClick={run} disabled={busy}>{busy ? 'Searching…' : 'Search'}</button>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={mode === 'ai'} onChange={e => setMode(e.target.checked ? 'ai' : 'keyword')} />
        AI search <span className="text-stone-500">(off = plain Brickset keyword search)</span>
      </label>
      <Err>{err}</Err>

      {results && results.length === 0 && <p className="text-stone-500">No matches. Try different words{mode === 'ai' ? ' or turn off AI search' : ''}.</p>}
      {results && !picked && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {results.map(c => (
            <li key={c.set_id}>
              <button onClick={() => setPicked(c)} className="flex w-full gap-3 rounded-xl bg-white p-3 text-left shadow-sm ring-1 ring-stone-200 hover:ring-brick dark:bg-stone-900 dark:ring-stone-800">
                {c.image_url ? <img src={c.image_url} className="h-20 w-20 shrink-0 bg-white object-contain" alt="" /> : <div className="h-20 w-20 bg-stone-200" />}
                <div className="min-w-0 text-sm">
                  <div className="font-medium">{c.name}</div>
                  <div className="text-stone-500">{c.number} · {c.year} · {c.theme}</div>
                  {c.reason && <div className="mt-1 text-xs italic text-stone-500">{c.reason}</div>}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {picked && (
        <div className="space-y-3 rounded-xl bg-white p-4 ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800">
          <div className="font-medium">Add “{picked.name}” ({picked.number})</div>
          <label className="block text-sm font-medium">Box
            <input className={input + ' font-mono'} list="boxes" value={box} onChange={e => setBox(e.target.value)} placeholder="e.g. 587B" autoFocus />
            <datalist id="boxes">{boxes.map(b => <option key={b} value={b} />)}</datalist>
          </label>
          <label className="block text-sm font-medium">Tags<TagInput value={tags} onChange={setTags} suggestions={allTags} /></label>
          <label className="block text-sm font-medium">Notes<textarea className={input} rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></label>
          <div className="flex gap-2"><button className={btnPrimary} onClick={save}>Add to collection</button>
            <button className={btnGhost} onClick={() => setPicked(null)}>Back to results</button></div>
        </div>
      )}
      {added.length > 0 && <ul className="text-sm text-green-700 dark:text-green-400">{added.map((a, i) => <li key={i}>✓ {a}</li>)}</ul>}
    </div>
  )
}

function AddOther() {
  const [title, setTitle] = useState(''); const [desc, setDesc] = useState(''); const [box, setBox] = useState('')
  const [tags, setTags] = useState(''); const [err, setErr] = useState(''); const [ok, setOk] = useState('')
  const submit = async () => {
    setErr(''); setOk('')
    try { await api.create({ type: 'other', title, description: desc, box, tags: splitTags(tags) }); setOk(`✓ ${title} → ${box || 'no box'}`); setTitle(''); setDesc('') }
    catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-stone-500">For anything that isn’t a set: loose parts, minifigs, spares, separators…</p>
      <input className={input} placeholder="What is it?" value={title} onChange={e => setTitle(e.target.value)} />
      <textarea className={input} rows={3} placeholder="Description (optional)" value={desc} onChange={e => setDesc(e.target.value)} />
      <input className={input + ' font-mono'} placeholder="Box, e.g. 587B" value={box} onChange={e => setBox(e.target.value)} />
      <TagInput value={tags} onChange={setTags} suggestions={[]} />
      <Err>{err}</Err>{ok && <p className="text-sm text-green-700 dark:text-green-400">{ok}</p>}
      <button className={btnPrimary} onClick={submit}>Add item</button>
    </div>
  )
}

export default function AddPage() {
  const [tab, setTab] = useState<'set' | 'other'>('set')
  const t = (k: 'set' | 'other', label: string) => (
    <button onClick={() => setTab(k)} className={`rounded-lg px-4 py-1.5 text-sm font-medium ${tab === k ? 'bg-brick text-white' : 'hover:bg-stone-200 dark:hover:bg-stone-800'}`}>{label}</button>
  )
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex gap-2">{t('set', 'Lego set')}{t('other', 'Other item')}</div>
      {tab === 'set' ? <AddSet /> : <AddOther />}
    </div>
  )
}
