import { createContext, useContext } from 'react'
import { setToken, type User } from '@/lib/api'

export interface AuthCtx {
  user: User
  logout: () => void
}
export const Ctx = createContext<AuthCtx | null>(null)
export const useAuth = () => {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside <RequireAuth>')
  return c
}

export function logout() {
  setToken(null)
  location.assign('/login')
}
