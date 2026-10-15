import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
export function Audit() {
  const { data, loading, error } = useAsync((s) => api.audit(s))
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Audit" description="Append-only decision history." />
      <p className="text-sm text-muted-foreground">Every decision keeps the original recommendation beside the final outcome. Entries cannot be edited or deleted.</p>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {data?.length === 0 && <p className="text-sm text-muted-foreground">No decisions yet.</p>}
      {data?.map((d) => (
        <Card key={d.id} className="p-3 text-sm">
          <p className="font-medium">
            <Link className="underline" to={`/logs/${d.log_id}`}>Log #{d.log_id}</Link> · <span className="capitalize">{d.action}</span> by {d.user}
          </p>
          <p>Original {d.original.priority} → final {d.final.priority}</p>
          {d.comment && <p className="text-muted-foreground">“{d.comment}”</p>}
          <p className="text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()}</p>
        </Card>
      ))}
    </div>
  )
}
