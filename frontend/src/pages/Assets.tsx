import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'
import type { AssetSummary } from '@/lib/types'

export function Assets() {
  const { data, loading, error } = useAsync<AssetSummary[]>((s) => api.assets(s))
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    if (!q) return data
    return data.filter(
      (a) =>
        a.unified_id.toLowerCase().includes(q) ||
        (a.asset_name ?? '').toLowerCase().includes(q) ||
        a.identifiers.some((i) => i.value.toLowerCase().includes(q)),
    )
  }, [data, query])

  return (
    <>
      <PageHeader
        eyebrow={data ? `Canonical model · ${data.length} assets` : 'Canonical model'}
        title="Assets"
        description="Every physical thing resolved to exactly one canonical record. System-specific codes are aliases, never separate assets."
      />

      <div className="relative mb-5 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, id, or identifier…"
          className="pl-9"
        />
      </div>

      {loading ? (
        <Card className="gap-3 py-5">
          <div className="space-y-3 px-5">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-6 w-1/3" />
          </div>
        </Card>
      ) : error ? (
        <Card className="py-5">
          <p className="px-5 text-sm text-critical">
            Couldn't load assets. Is the backend running?
          </p>
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="py-10">
          <p className="px-5 text-center text-sm text-muted-foreground">
            {data && data.length === 0
              ? 'No assets resolved yet. Ingest a source system to begin.'
              : 'No assets match your search.'}
          </p>
        </Card>
      ) : (
        <Card className="gap-0 divide-y divide-border/60 py-0">
          {filtered.map((a) => (
            <AssetRow key={a.unified_id} asset={a} />
          ))}
        </Card>
      )}
    </>
  )
}

function AssetRow({ asset }: { asset: AssetSummary }) {
  return (
    <div className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-sm font-semibold">
            {asset.asset_name || asset.unified_id}
          </h3>
          {asset.needs_review && <Badge variant="review">Needs review</Badge>}
        </div>
        <p className="font-mono text-xs text-muted-foreground">{asset.unified_id}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {asset.identifiers.length > 0 ? (
          asset.identifiers.map((i, idx) => (
            <Badge
              key={idx}
              variant={i.is_primary ? 'linked' : 'neutral'}
              className="font-mono"
              title={i.concept}
            >
              {i.concept.replace(/_/g, ' ')}: {i.value}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">No identifiers</span>
        )}
      </div>
    </div>
  )
}
