import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, History, Loader2, Play, ShieldAlert, ShieldCheck } from 'lucide-react'

import { HistoryDialog } from '@/components/workflows/WorkflowViews'
import { Badge, StatusDot } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { streamWorkflow } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { ComplianceResult, WorkflowEvent } from '@/lib/types'

const POSTURE: Record<
  string,
  { label: string; variant: 'verified' | 'critical' | 'neutral'; icon: typeof ShieldCheck }
> = {
  compliant: { label: 'Compliant', variant: 'verified', icon: ShieldCheck },
  at_risk: { label: 'At risk', variant: 'critical', icon: ShieldAlert },
  unknown: { label: 'Unknown', variant: 'neutral', icon: ShieldAlert },
}

export function Compliance() {
  const [rule, setRule] = useState('')
  const [asset, setAsset] = useState('')
  const [question, setQuestion] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState<ComplianceResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  async function run() {
    if ((!rule.trim() && !asset.trim()) || streaming) return
    setStreaming(true)
    setResult(null)
    setError(null)
    setStatus('Starting compliance analysis')
    const controller = new AbortController()
    abortRef.current = controller
    try {
      for await (const ev of streamWorkflow(
        '/api/compliance',
        {
          question: question.trim(),
          rule: rule.trim() || null,
          asset: asset.trim() || null,
        },
        controller.signal,
      ) as AsyncGenerator<WorkflowEvent>) {
        if (ev.step === 'complete') setResult((ev.result as ComplianceResult) ?? null)
        if (ev.message) setStatus(ev.message)
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        setError(e instanceof Error ? e.message : 'Request failed')
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const narrative = result?.narrative
  const posture = POSTURE[narrative?.posture ?? 'unknown'] ?? POSTURE.unknown
  const atRisk = result?.at_risk_assets ?? []

  return (
    <>
      <div className="mb-6 flex items-center justify-between gap-3">
        <Button variant="outline" size="sm" asChild>
          <Link to="/workflows">
            <ArrowLeft />
            Back to Workflows
          </Link>
        </Button>
        <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)}>
          <History />
          History
        </Button>
      </div>

      <div className="mb-6">
        <Badge variant="linked">Compliance</Badge>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-[1.75rem]">
          Compliance review
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Start from a rule or an asset. The at-risk list is computed from
          records, not written by the model. Every clause traces back to evidence.
        </p>
      </div>

      <Card className="mb-6 gap-4 py-5">
        <div className="grid gap-3 px-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="text-sm">
            <span className="mb-1.5 block font-medium">Rule</span>
            <Input
              value={rule}
              onChange={(e) => setRule(e.target.value)}
              placeholder="e.g. RULE-LUBE-001"
              disabled={streaming}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1.5 block font-medium">or Asset</span>
            <Input
              value={asset}
              onChange={(e) => setAsset(e.target.value)}
              placeholder="e.g. PMP-101, a tag, or asset id"
              disabled={streaming}
            />
          </label>
          <Button onClick={run} disabled={streaming || (!rule.trim() && !asset.trim())}>
            {streaming ? <Loader2 className="animate-spin" /> : <Play />}
            Review
          </Button>
        </div>
        <label className="px-5 text-sm">
          <span className="mb-1.5 block font-medium">
            Narrow the question{' '}
            <span className="font-normal text-muted-foreground">— optional</span>
          </span>
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Are any lubrication rules overdue this quarter?"
            disabled={streaming}
          />
        </label>
        <p className="px-5 text-xs text-muted-foreground">
          The question only shapes the written summary. The at-risk list is always
          computed from the records — the model can't add to or remove from it.
        </p>
      </Card>

      <HistoryDialog kind="compliance" open={historyOpen} onClose={() => setHistoryOpen(false)} />

      {streaming && (
        <Card className="mb-6 py-4">
          <p className="flex items-center gap-2 px-5 text-sm text-muted-foreground">
            <StatusDot className="motion-safe:animate-pulse" />
            {status}…
          </p>
        </Card>
      )}

      {error && (
        <Card className="mb-6 py-4">
          <p className="px-5 text-sm text-critical">{error}</p>
        </Card>
      )}

      {result && (
        <div className="space-y-5">
          <Card className="py-5">
            <div className="flex flex-wrap items-center justify-between gap-3 px-5">
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    'flex size-10 items-center justify-center rounded-xl',
                    posture.variant === 'critical'
                      ? 'bg-critical-soft text-critical'
                      : posture.variant === 'verified'
                        ? 'bg-verified-soft text-verified'
                        : 'bg-secondary text-muted-foreground',
                  )}
                >
                  <posture.icon className="size-5" />
                </span>
                <div>
                  <p className="text-sm text-muted-foreground">Compliance posture</p>
                  <div className="flex items-center gap-2">
                    <Badge variant={posture.variant === 'neutral' ? 'neutral' : posture.variant}>
                      {posture.label}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {atRisk.length} asset{atRisk.length === 1 ? '' : 's'} at risk
                    </span>
                  </div>
                </div>
              </div>
              <Badge variant="outline">Evidence from {result.evidence_from}</Badge>
            </div>
            {narrative && (
              <p className="mt-4 px-5 text-sm leading-relaxed">{narrative.summary}</p>
            )}
          </Card>

          {atRisk.length > 0 && (
            <Card className="gap-0 divide-y divide-border/60 py-0">
              <div className="px-5 py-4">
                <h2 className="text-base font-semibold">At-risk assets</h2>
                <p className="text-sm text-muted-foreground">
                  Computed from the graph — subject to a rule with no completed work order.
                </p>
              </div>
              {atRisk.map((a, i) => (
                <div key={i} className="flex items-start gap-3 px-5 py-4">
                  <StatusDot tone="critical" className="mt-1.5" />
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-medium">{a.asset}</p>
                    <p className="text-sm text-muted-foreground">{a.reason}</p>
                  </div>
                  <Badge variant="critical" className="ml-auto">
                    {a.rule}
                  </Badge>
                </div>
              ))}
            </Card>
          )}

          {narrative &&
            (narrative.contradictions.length > 0 || narrative.unresolved.length > 0) && (
              <Card className="py-5">
                <div className="space-y-4 px-5">
                  {narrative.contradictions.length > 0 && (
                    <div>
                      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-critical">
                        <StatusDot tone="critical" />
                        Contradicting evidence
                      </p>
                      <ul className="space-y-1.5">
                        {narrative.contradictions.map((c, i) => (
                          <li key={i} className="rounded-lg bg-critical-soft px-3 py-2 text-sm">
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {narrative.unresolved.length > 0 && (
                    <div>
                      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-minor">
                        <StatusDot tone="minor" />
                        Unresolved — open questions
                      </p>
                      <ul className="space-y-1.5">
                        {narrative.unresolved.map((c, i) => (
                          <li key={i} className="rounded-lg bg-minor-soft px-3 py-2 text-sm">
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>
            )}
        </div>
      )}
    </>
  )
}
