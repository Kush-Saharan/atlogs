import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, getToken, type User } from '@/lib/api'
import { Ctx, logout } from '@/lib/session'

/** Route guard: loads the current user; no/invalid token goes to /login.
 *  `roles` limits a route to those roles (others are sent home). */
export function RequireAuth({
  roles,
  children,
}: {
  roles?: User['role'][]
  children: React.ReactNode
}) {
  const [user, setUser] = useState<User | null>(null)
  const [failed, setFailed] = useState(!getToken())
  useEffect(() => {
    if (!getToken()) return
    api.me().then(setUser).catch(() => setFailed(true))
  }, [])
  if (failed) return <Navigate to="/login" replace />
  if (!user) return null
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>
}
