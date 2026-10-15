import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import type { ScheduleProposal } from '@/lib/types'
import { useAsync } from '@/lib/useAsync'

function msg(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback
}

const REASON = { skill: 'No skilled technician', availability: 'No free time slot', part: 'Part out of stock' }

function Proposal() {
  const { data, loading, error, reload } = useAsync((s) => api.scheduleProposal(s))
  const [fresh, setFresh] = useState<ScheduleProposal | null>(null)
  const [days, setDays] = useState('14')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const p = fresh ?? data

  async function run(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { setFresh(await api.proposeSchedule(Number(days))) } catch (x) { setErr(msg(x, 'Could not propose a schedule')) }
    setBusy(false)
    reload()
  }

  return (
    <section aria-labelledby="prop-h" className="flex flex-col gap-3">
      <h2 id="prop-h" className="text-lg font-semibold">Proposed schedule</h2>
      <Card className="p-4">
        <form onSubmit={run} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">Days ahead
            <Input type="number" min={1} max={60} required value={days} onChange={(e) => setDays(e.target.value)} className="w-24" /></label>
          <Button type="submit" disabled={busy}>{busy ? 'Proposing…' : 'Propose schedule'}</Button>
        </form>
        <p className="mt-2 text-sm text-muted-foreground">
          A proposal for all pending recommendations. Nothing is booked and part stock is unchanged until a manager decides.
        </p>
        {err && <p role="alert" className="mt-2 text-sm text-destructive">{err}</p>}
      </Card>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!loading && !p && <p className="text-sm text-muted-foreground">No proposal yet.</p>}
      {p && (
        <>
          <p className="text-sm text-muted-foreground">
            Proposal #{p.id}, {p.horizon_start.slice(0, 16).replace('T', ' ')} to {p.horizon_end.slice(0, 16).replace('T', ' ')}
          </p>
          <h3 className="font-medium">Assignments ({p.assignments.length})</h3>
          {p.assignments.length === 0 && <p className="text-sm text-muted-foreground">Nothing could be scheduled.</p>}
          {p.assignments.map((a) => (
            <Card key={a.recommendation_id} className="p-3 text-sm">
              <p className="font-medium">
                {a.priority} · <Link className="underline" to={`/logs/${a.log_id}`}>Log #{a.log_id}</Link> · {a.technician}
              </p>
              <p className="text-muted-foreground">
                {a.start.slice(0, 16).replace('T', ' ')} to {a.end.slice(0, 16).replace('T', ' ')}
                {a.parts.length > 0 && ` · parts: ${a.parts.join(', ')}`}
              </p>
            </Card>
          ))}
          <h3 className="font-medium">Conflicts ({p.conflicts.length})</h3>
          {p.conflicts.length === 0 && <p className="text-sm text-muted-foreground">No conflicts.</p>}
          {p.conflicts.map((c) => (
            <Card key={c.recommendation_id} className="border-destructive/50 p-3 text-sm">
              <p className="font-medium">
                {c.priority} · <Link className="underline" to={`/logs/${c.log_id}`}>Log #{c.log_id}</Link> · {REASON[c.reason]}
              </p>
              <p className="text-muted-foreground">{c.detail}. Priority is unchanged; escalate or add the resource.</p>
            </Card>
          ))}
        </>
      )}
    </section>
  )
}

function Defaults() {
  const { data, loading, error, reload } = useAsync((s) => api.scheduleDefaults(s))
  const [component, setComponent] = useState('')
  const [skill, setSkill] = useState('')
  const [mins, setMins] = useState('60')
  const [parts, setParts] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await api.saveScheduleDefault(component.trim(), {
        skill, duration_min: Number(mins), parts: parts.split(',').map((s) => s.trim()).filter(Boolean),
      })
      setComponent(''); setSkill(''); setMins('60'); setParts('')
      reload()
    } catch (x) { setFormError(msg(x, 'Could not save')) }
  }
  async function remove(c: string) {
    try { await api.deleteScheduleDefault(c) } catch (x) { setFormError(msg(x, 'Could not delete')) }
    reload()
  }

  return (
    <section aria-labelledby="def-h" className="flex flex-col gap-3">
      <h2 id="def-h" className="text-lg font-semibold">Component defaults</h2>
      <p className="text-sm text-muted-foreground">
        Required skill, duration and parts per component. Components not listed need the skill "general" for 60 minutes.
      </p>
      <Card className="p-4">
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">Component
            <Input required value={component} onChange={(e) => setComponent(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Skill
            <Input required value={skill} onChange={(e) => setSkill(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Minutes
            <Input type="number" min={1} required value={mins} onChange={(e) => setMins(e.target.value)} className="w-24" /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Parts (comma separated)
            <Input value={parts} onChange={(e) => setParts(e.target.value)} /></label>
          <Button type="submit">Save default</Button>
        </form>
        {formError && <p role="alert" className="mt-2 text-sm text-destructive">{formError}</p>}
      </Card>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data?.map((d) => (
        <Card key={d.component} className="flex items-center justify-between gap-3 p-3">
          <p className="text-sm">
            <span className="font-medium">{d.component}</span>
            <span className="text-muted-foreground"> · {d.skill} · {d.duration_min} min · {d.parts.join(', ') || 'no parts'}</span>
          </p>
          <div className="flex gap-2">
            <Button variant="outline" aria-label={`Edit ${d.component}`}
              onClick={() => { setComponent(d.component); setSkill(d.skill); setMins(String(d.duration_min)); setParts(d.parts.join(', ')) }}>Edit</Button>
            <Button variant="outline" aria-label={`Delete ${d.component}`} onClick={() => remove(d.component)}>Delete</Button>
          </div>
        </Card>
      ))}
    </section>
  )
}

export function Schedule() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Schedule" description="Resource-aware schedule proposal." />
      <Proposal />
      <Defaults />
    </div>
  )
}
