import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, LogSubmitError, submitLog } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

export function Logs() {
  const { data, loading, error, reload } = useAsync((s) => api.logs(s))
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [duplicate, setDuplicate] = useState(false)

  async function send(force: boolean) {
    setBusy(true)
    setMessage(null)
    setDuplicate(false)
    try {
      await submitLog({ text, file, force })
      setText('')
      setFile(null)
      reload()
    } catch (err) {
      if (err instanceof LogSubmitError) {
        setDuplicate(err.status === 409)
        setMessage(err.existingId ? `${err.message} (existing log #${err.existingId})` : err.message)
      } else {
        setMessage('Could not submit the log')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Maintenance logs" />
      <Card className="flex flex-col gap-3 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void send(false)
          }}
          className="flex flex-col gap-3"
        >
          <label className="flex flex-col gap-1 text-sm font-medium">
            Paste a log
            <Textarea value={text} onChange={(e) => setText(e.target.value)} disabled={!!file}
              placeholder="Pump P-104 experienced excessive vibration near its motor bearing..." />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Or upload a file (.txt, .log, .csv, max 1 MB)
            <input type="file" accept=".txt,.log,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm font-normal" />
          </label>
          <div>
            <Button type="submit" disabled={busy || (!file && !text.trim())}>
              {busy ? 'Submitting…' : 'Submit log'}
            </Button>
          </div>
        </form>
        {message && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
            <span>{message}</span>
            {duplicate && (
              <Button type="button" variant="outline" disabled={busy} onClick={() => void send(true)}>
                Submit anyway
              </Button>
            )}
          </div>
        )}
      </Card>
      {loading && <Skeleton className="h-24 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data?.length === 0 && <p className="text-sm text-muted-foreground">No logs yet.</p>}
      <div className="flex flex-col gap-2">
        {data?.map((l) => (
          <Card key={l.id} className="flex items-start justify-between gap-3 p-3">
            <div className="min-w-0">
              <p className="text-sm font-medium">
                <Link to={`/logs/${l.id}`} className="underline underline-offset-2">
                  #{l.id}{l.filename ? ` · ${l.filename}` : ''}
                </Link>
              </p>
              <p className="truncate text-sm text-muted-foreground">{l.preview}</p>
              {l.error && <p className="text-sm text-destructive">{l.error}</p>}
            </div>
            <Badge>{l.status}</Badge>
          </Card>
        ))}
      </div>
    </div>
  )
}
