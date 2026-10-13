import { useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

function msg(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback
}

function Technicians() {
  const { data, loading, error, reload } = useAsync((s) => api.technicians(s))
  const [name, setName] = useState('')
  const [skills, setSkills] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  async function add(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await api.saveTechnician({
        name,
        skills: skills.split(',').map((s) => s.trim()).filter(Boolean),
        availability: start && end ? [{ start, end }] : [],
      })
      setName(''); setSkills(''); setStart(''); setEnd('')
      reload()
    } catch (err) {
      setFormError(msg(err, 'Could not save technician'))
    }
  }
  async function remove(id: number) {
    try { await api.deleteTechnician(id) } catch (err) { setFormError(msg(err, 'Could not delete')) }
    reload()
  }

  return (
    <section aria-labelledby="tech-h" className="flex flex-col gap-3">
      <h2 id="tech-h" className="text-lg font-semibold">Technicians</h2>
      <Card className="p-4">
        <form onSubmit={add} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">Name
            <Input required value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Skills (comma separated)
            <Input value={skills} onChange={(e) => setSkills(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Available from
            <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Available until
            <Input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
          <Button type="submit">Add technician</Button>
        </form>
        {formError && <p role="alert" className="mt-2 text-sm text-destructive">{formError}</p>}
      </Card>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data?.length === 0 && <p className="text-sm text-muted-foreground">No technicians yet.</p>}
      {data?.map((t) => (
        <Card key={t.id} className="flex items-center justify-between gap-3 p-3">
          <div className="text-sm">
            <p className="font-medium">{t.name}</p>
            <p className="text-muted-foreground">
              {t.skills.join(', ') || 'no skills'}
              {t.availability.map((w) => ` · ${w.start} to ${w.end}`).join('')}
            </p>
          </div>
          <Button variant="outline" onClick={() => remove(t.id)} aria-label={`Delete ${t.name}`}>Delete</Button>
        </Card>
      ))}
    </section>
  )
}

function Parts() {
  const { data, loading, error, reload } = useAsync((s) => api.parts(s))
  const [name, setName] = useState('')
  const [stock, setStock] = useState('0')
  const [formError, setFormError] = useState<string | null>(null)

  async function add(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    try {
      await api.savePart({ name, stock: Number(stock) })
      setName(''); setStock('0')
      reload()
    } catch (err) {
      setFormError(msg(err, 'Could not save part'))
    }
  }
  async function setPartStock(id: number, partName: string, value: string) {
    setFormError(null)
    try { await api.savePart({ name: partName, stock: Number(value) }, id) } catch (err) { setFormError(msg(err, 'Could not update stock')) }
    reload()
  }
  async function remove(id: number) {
    try { await api.deletePart(id) } catch (err) { setFormError(msg(err, 'Could not delete')) }
    reload()
  }

  return (
    <section aria-labelledby="parts-h" className="flex flex-col gap-3">
      <h2 id="parts-h" className="text-lg font-semibold">Parts</h2>
      <Card className="p-4">
        <form onSubmit={add} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">Name
            <Input required value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm font-medium">Stock
            <Input type="number" min={0} required value={stock} onChange={(e) => setStock(e.target.value)} /></label>
          <Button type="submit">Add part</Button>
        </form>
        {formError && <p role="alert" className="mt-2 text-sm text-destructive">{formError}</p>}
      </Card>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data?.length === 0 && <p className="text-sm text-muted-foreground">No parts yet.</p>}
      {data?.map((p) => (
        <Card key={p.id} className="flex items-center justify-between gap-3 p-3">
          <span className="text-sm font-medium">{p.name}</span>
          <div className="flex items-center gap-2">
            <Input type="number" min={0} defaultValue={p.stock} className="w-24"
              aria-label={`Stock for ${p.name}`}
              onBlur={(e) => e.target.value !== String(p.stock) && setPartStock(p.id, p.name, e.target.value)} />
            <Button variant="outline" onClick={() => remove(p.id)} aria-label={`Delete ${p.name}`}>Delete</Button>
          </div>
        </Card>
      ))}
    </section>
  )
}

export function Resources() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Resources" description="Technicians and parts used for scheduling. Equipment criticality is set on the Assets page." />
      <Technicians />
      <Parts />
    </div>
  )
}
