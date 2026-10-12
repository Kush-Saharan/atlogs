import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { LOG_FIELDS, type ExtractedField, type MaintenanceLogDetail } from '@/lib/types'
import { useAsync } from '@/lib/useAsync'

/** Source text with extracted spans marked. Each mark carries a visible field label, so the
 *  highlight never relies on colour alone. Overlapping spans are skipped (first wins). */
function Highlighted({ text, fields }: { text: string; fields: Record<string, ExtractedField | null> }) {
  const spans = Object.entries(fields)
    .flatMap(([name, f]) => (f ? [{ name, f }] : []))
    .sort((a, b) => a.f.span[0] - b.f.span[0])
  const parts: React.ReactNode[] = []
  let pos = 0
  for (const { name, f } of spans) {
    const [s, e] = f.span
    if (s < pos) continue
    parts.push(<Fragment key={`t${s}`}>{text.slice(pos, s)}</Fragment>)
    parts.push(
      <mark key={`m${s}`} className="rounded bg-primary/20 px-0.5 text-foreground">
        {text.slice(s, e)}
        <sup className="ml-0.5 text-[10px] font-semibold uppercase">
          {name}{f.needs_review ? ' (needs review)' : ''}
        </sup>
      </mark>,
    )
    pos = e
  }
  parts.push(<Fragment key="end">{text.slice(pos)}</Fragment>)
  return <p className="whitespace-pre-wrap text-sm leading-relaxed">{parts}</p>
}

export function LogReview() {
  const { id } = useParams()
  const { data, loading, error } = useAsync((s) => api.log(Number(id), s), [id])
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={`Log #${id}`} action={<Link to="/logs" className="text-sm underline">Back to logs</Link>} />
      {loading && <Skeleton className="h-40 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data && <ReviewBody key={data.id} initial={data} />}
    </div>
  )
}

function ReviewBody({ initial }: { initial: MaintenanceLogDetail }) {
  const logId = initial.id
  const { user } = useAuth()
  const canReview = user.role === 'engineer' || user.role === 'admin'
  const [log, setLog] = useState(initial)
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(LOG_FIELDS.map((k) => [
      k, initial.record?.reviewed?.[k] ? (initial.record.reviewed[k].value ?? '')
        : (initial.record?.extracted.fields[k]?.value ?? '')])))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setMessage(null)
    try {
      setLog(await api.reviewLog(logId, values))
      setMessage('Review saved')
    } catch {
      setMessage('Could not save the review')
    } finally {
      setBusy(false)
    }
  }

  const fields = log.record?.extracted.fields ?? {}
  return (
    <>
          <p className="text-sm">Status: <Badge>{log.status}</Badge>
            {log.record?.reviewed_at && ` · reviewed ${new Date(log.record.reviewed_at).toLocaleString()}`}
          </p>
          {log.error && <p role="alert" className="text-sm text-destructive">{log.error}</p>}
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-4">
              <h2 className="mb-2 text-sm font-semibold">Source text (never edited)</h2>
              <Highlighted text={log.original_text} fields={fields} />
            </Card>
            <Card className="p-4">
              <h2 className="mb-2 text-sm font-semibold">Fields</h2>
              {!log.record ? (
                <p className="text-sm text-muted-foreground">No extracted record for this log.</p>
              ) : (
                <form onSubmit={(e) => { e.preventDefault(); void save() }} className="flex flex-col gap-3">
                  {LOG_FIELDS.map((k) => {
                    const f = fields[k]
                    return (
                      <div key={k} className="flex flex-col gap-1">
                        <label htmlFor={`f-${k}`} className="flex flex-wrap items-center gap-2 text-sm font-medium capitalize">
                          {k}
                          {f?.needs_review && <Badge>Needs review</Badge>}
                          {!f && <span className="text-xs font-normal text-muted-foreground">Not found</span>}
                          {f && (
                            <span className="text-xs font-normal text-muted-foreground">
                              confidence {Math.round(f.confidence * 100)}% · {f.source}
                            </span>
                          )}
                        </label>
                        <input id={`f-${k}`} value={values[k] ?? ''} disabled={!canReview}
                          onChange={(e) => setValues({ ...values, [k]: e.target.value })}
                          className="h-9 rounded-md border border-input bg-background px-2 text-sm" />
                        {f && values[k] !== f.value && (
                          <span className="text-xs text-muted-foreground">Extracted: {f.value}</span>
                        )}
                      </div>
                    )
                  })}
                  {canReview ? (
                    <div><Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save review'}</Button></div>
                  ) : (
                    <p className="text-sm text-muted-foreground">Only engineers can edit fields.</p>
                  )}
                  {message && <p role="status" className="text-sm">{message}</p>}
                </form>
              )}
            </Card>
          </div>
    </>
  )
}
