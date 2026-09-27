import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import {
  login as apiLogin,
  logout as apiLogout,
  getMe,
  clearTokens,
  getAccessToken,
  getLoginErrorMessage,
  type ApiUser,
} from './api'
import { trackLogin, trackLogout } from './telemetry'

interface AuthState {
  user: ApiUser | null
  loading: boolean
  error: string | null
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  })

  // Restore session on mount
  useEffect(() => {
    const init = async () => {
      const token = getAccessToken()
      if (!token) {
        setState({ user: null, loading: false, error: null })
        return
      }

      try {
        const user = await getMe()
        setState({ user, loading: false, error: null })
      } catch {
        clearTokens()
        setState({ user: null, loading: false, error: null })
      }
    }
    init()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setState((s) => ({ ...s, error: null, loading: true }))
    try {
      const data = await apiLogin(email, password)
      setState({ user: data.user, loading: false, error: null })
      trackLogin() // real-time login moment: time, IP-side metadata, geo consent prompt
    } catch (err: unknown) {
      const message = getLoginErrorMessage(err)
      setState((s) => ({ ...s, loading: false, error: message }))
      throw err
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      trackLogout() // flush LOGOUT_TIME before the session context dies
      setState({ user: null, loading: false, error: null })
    }
  }, [])

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
