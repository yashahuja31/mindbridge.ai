/**
 * JWT auth for the SPA. The token lives in localStorage so a refresh keeps you signed in; on load
 * (and whenever the token changes) we validate it against `GET /auth/me` and drop it if it's stale.
 * Matching works without an account — being signed in only adds saved history.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import * as api from '@/lib/api'
import type { Role, User } from '@/types'

const TOKEN_KEY = 'mindbridge_token'

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (email: string, password: string, role: Role) => Promise<User>
  /** Adopt a ready-made token (OAuth callback fragment); resolves to the validated user. */
  loginWithToken: (accessToken: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState<boolean>(() => localStorage.getItem(TOKEN_KEY) !== null)

  // Validate the current token whenever it changes (including the initial page load).
  useEffect(() => {
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    api
      .me(token)
      .then((u) => {
        if (!cancelled) setUser(u)
      })
      .catch(() => {
        if (cancelled) return
        localStorage.removeItem(TOKEN_KEY)
        setToken(null)
        setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const adopt = useCallback((accessToken: string, u: User) => {
    localStorage.setItem(TOKEN_KEY, accessToken)
    setUser(u)
    setToken(accessToken) // re-validates via the effect, but we already have the user
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api.login(email, password)
      const u = await api.me(access_token)
      adopt(access_token, u)
      return u
    },
    [adopt],
  )

  const register = useCallback(
    async (email: string, password: string, role: Role) => {
      const { access_token } = await api.register(email, password, role)
      const u = await api.me(access_token)
      adopt(access_token, u)
      return u
    },
    [adopt],
  )

  const loginWithToken = useCallback(
    async (accessToken: string) => {
      const u = await api.me(accessToken) // validate before trusting anything from a URL
      adopt(accessToken, u)
      return u
    },
    [adopt],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, token, loading, login, register, loginWithToken, logout }),
    [user, token, loading, login, register, loginWithToken, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- hook co-located with its provider
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
