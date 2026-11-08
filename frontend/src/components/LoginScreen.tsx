import { btnPrimary } from './ui'

const messages: Record<string, string> = {
  not_allowed: 'That Google account is not allowed to use this app. Sign in with the account the owner configured.',
  failed: 'Sign-in did not complete. Please try again (make sure cookies are enabled).',
}

export default function LoginScreen() {
  const err = messages[new URLSearchParams(window.location.search).get('login_error') ?? '']
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-5 rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800">
        <div className="text-5xl">🧱</div>
        <h1 className="text-2xl font-bold text-brick">Lego Organizer</h1>
        <p className="text-sm text-stone-500">This is a private collection. Please sign in to continue.</p>
        {err && <p className="rounded-lg bg-red-100 px-3 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{err}</p>}
        <a href="/auth/login" className={btnPrimary + ' inline-block w-full py-2.5'}>Sign in with Google</a>
        <p className="text-xs text-stone-400">Access is limited to a single approved account.</p>
      </div>
    </div>
  )
}
