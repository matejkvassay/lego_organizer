import { useEffect, useState } from 'react'
import { getMe, type Me } from './api'
import LoginScreen from './components/LoginScreen'
import AddPage from './components/AddPage'
import Collection from './components/Collection'
import ItemPage from './components/ItemPage'
import { href, useRoute } from './route'
import { btnGhost, btnPrimary, input } from './components/ui'

export default function App() {
  const route = useRoute()
  const [q, setQ] = useState(route.filters.q ?? '')
  const [me, setMe] = useState<Me | null | undefined>(undefined)  // undefined = checking, null = signed out
  useEffect(() => {
    getMe().then(setMe).catch(() => setMe(null))
    const out = () => setMe(null)
    window.addEventListener('unauthorized', out)
    return () => window.removeEventListener('unauthorized', out)
  }, [])
  if (me === undefined) return null
  if (me === null) return <LoginScreen />
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-white/90 backdrop-blur dark:border-stone-800 dark:bg-stone-950/90">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <a href="#/" className="text-lg font-bold text-brick">🧱 Lego Organizer</a>
          <form className="flex-1" onSubmit={e => { e.preventDefault(); window.location.hash = href({ q }) }}>
            <input className={input} placeholder="Search your collection (name, number, theme, box, tag, notes)…" value={q} onChange={e => setQ(e.target.value)} />
          </form>
          <a className={btnPrimary} href="#/add">+ Add</a>
          <a className={btnGhost} href="/api/export.csv" title="Download CSV">CSV</a>
          <a className={btnGhost} href="/api/export.json" title="Download JSON">JSON</a>
          <div className="flex items-center gap-2 border-l border-stone-300 pl-4 text-sm dark:border-stone-700">
            <span className="hidden text-right leading-tight sm:block">
              <span className="block text-xs text-stone-500">Signed in as</span>
              <span className="block max-w-48 truncate font-medium">{me.email}</span>
            </span>
            <a className={btnGhost} href="/auth/logout">Log out</a>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        {route.page === 'add' && <AddPage />}
        {route.page === 'item' && <ItemPage id={route.id!} />}
        {route.page === 'home' && <Collection filters={route.filters} />}
      </main>
    </div>
  )
}
