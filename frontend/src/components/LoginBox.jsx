import { useState } from 'react'
import { useAuth } from '../auth/AuthContext.jsx'
import { useI18n } from '../i18n/LanguageContext.jsx'
import { errorText } from '../lib/errors.js'

export default function LoginBox() {
  const { t } = useI18n()
  const { user, login, logout } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)

  if (user) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span>
          {t('signedInAs')} <strong>{user.username}</strong> ({t(`role_${user.role}`)})
        </span>
        <button type="button" onClick={logout} className="min-h-[44px] rounded-lg border border-stone-300 px-3 font-semibold">
          {t('logout')}
        </button>
      </div>
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password)
      setPassword('')
    } catch (err) {
      setError(err.status === 401 ? t('err_badLogin') : errorText(err, t))
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2 text-sm" aria-label={t('login')}>
      <input
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder={t('username')}
        aria-label={t('username')}
        autoComplete="username"
        className="min-h-[44px] w-28 rounded-lg border border-stone-300 px-2"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={t('password')}
        aria-label={t('password')}
        autoComplete="current-password"
        className="min-h-[44px] w-28 rounded-lg border border-stone-300 px-2"
      />
      <button type="submit" disabled={!username || !password} className="min-h-[44px] rounded-lg bg-leaf px-3 font-bold text-white disabled:opacity-50">
        {t('login')}
      </button>
      {error && <p className="w-full text-red-700">{error}</p>}
    </form>
  )
}
