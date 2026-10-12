import { useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { useAsync } from '@/lib/useAsync'

const ROLES = ['engineer', 'manager', 'admin']

export function Users() {
  const { user: me } = useAuth()
  const { data, loading, error, reload } = useAsync((s) => api.users(s))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('engineer')
  const [formError, setFormError] = useState<string | null>(null)

  async function create(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await api.createUser({ email, password, role })
      setEmail('')
      setPassword('')
      reload()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not create user')
    }
  }

  async function setUserRole(id: number, newRole: string) {
    try {
      await api.updateUser(id, { role: newRole })
    } catch {
      setFormError('Could not change role')
    }
    reload()
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Users" />
      <Card className="p-4">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Email
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Password (min 8)
            <Input type="password" required minLength={8} autoComplete="new-password"
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}
              className="h-10 rounded-lg border border-border bg-card px-3 text-sm">
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <Button type="submit">Create user</Button>
        </form>
        {formError && <p role="alert" className="mt-2 text-sm text-destructive">{formError}</p>}
      </Card>
      {loading && <Skeleton className="h-24 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-col gap-2">
        {data?.map((u) => (
          <Card key={u.id} className="flex items-center justify-between gap-3 p-3">
            <span className="text-sm">{u.email}</span>
            <div className="flex items-center gap-2">
              {!u.active && <Badge>inactive</Badge>}
              <select aria-label={`Role for ${u.email}`} value={u.role} disabled={u.id === me.id}
                onChange={(e) => setUserRole(u.id, e.target.value)}
                className="h-9 rounded-lg border border-border bg-card px-2 text-sm">
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
