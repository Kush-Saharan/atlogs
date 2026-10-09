import { Link } from 'react-router-dom'
import {
  ArrowRight,
  FileText,
  Radio,
  ShieldCheck,
  Upload,
  type LucideIcon,
} from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Tone = 'verified' | 'review' | 'linked'

// Each workflow is colour-coded with its status tint: the icon well and the
// action button share the soft tone background (replacing the neutral/accent).
const TONE: Record<Tone, { icon: string; button: string }> = {
  verified: {
    icon: 'bg-verified-soft text-verified',
    button: 'bg-verified-soft text-verified hover:bg-verified-soft/70',
  },
  review: {
    icon: 'bg-review-soft text-review',
    button: 'bg-review-soft text-review hover:bg-review-soft/70',
  },
  linked: {
    icon: 'bg-linked-soft text-linked',
    button: 'bg-linked-soft text-linked hover:bg-linked-soft/70',
  },
}

interface WF {
  to: string
  icon: LucideIcon
  title: string
  tone: Tone
  cta: string
}

const WORKFLOWS: WF[] = [
  {
    to: '/workflows/documents',
    icon: FileText,
    title: 'Ingest documents (PDF)',
    tone: 'verified',
    cta: 'Open document ingestion',
  },
  {
    to: '/connectors',
    icon: Upload,
    title: 'Connect a source',
    tone: 'verified',
    cta: 'Open Connectors',
  },
  {
    to: '/workflows/rca',
    icon: Radio,
    title: 'Root cause analysis',
    tone: 'review',
    cta: 'Open RCA',
  },
  {
    to: '/workflows/compliance',
    icon: ShieldCheck,
    title: 'Compliance',
    tone: 'linked',
    cta: 'Open Compliance',
  },
]

export function Workflows() {
  return (
    <>
      <PageHeader title="Workflows" />
      <div className="flex flex-col gap-4">
        {WORKFLOWS.map((wf) => {
          const Icon = wf.icon
          const tone = TONE[wf.tone]
          return (
            <Card
              key={wf.to}
              className="flex flex-col gap-4 px-6 py-5 transition-colors hover:border-primary/30 sm:flex-row sm:items-center"
            >
              <div className="flex min-w-0 flex-1 items-center gap-4">
                <span
                  className={cn(
                    'flex size-11 shrink-0 items-center justify-center rounded-xl',
                    tone.icon,
                  )}
                >
                  <Icon className="size-5" />
                </span>
                <h2 className="min-w-0 text-base font-semibold">{wf.title}</h2>
              </div>
              <Button
                asChild
                variant="ghost"
                className={cn('w-full shadow-sm sm:w-auto', tone.button)}
              >
                <Link to={wf.to}>
                  {wf.cta}
                  <ArrowRight />
                </Link>
              </Button>
            </Card>
          )
        })}
      </div>
    </>
  )
}
