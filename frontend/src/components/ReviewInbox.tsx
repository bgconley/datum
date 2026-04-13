import { useEffect, useMemo, useState } from 'react'
import { Check, FilePenLine, Inbox, ShieldAlert, SlidersHorizontal, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useContextPanel } from '@/lib/context-panel'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

interface ReviewInboxProps {
  projectSlug: string
}

type CandidateKind = 'decision' | 'requirement' | 'open_question'

const CANDIDATE_KINDS: CandidateKind[] = ['decision', 'requirement', 'open_question']

function kindLabel(kind: CandidateKind): string {
  return kind.replace('_', ' ')
}

export function ReviewInbox({ projectSlug }: ReviewInboxProps) {
  const [sortMode, setSortMode] = useState<'confidence' | 'severity'>('confidence')
  const [kindFilter, setKindFilter] = useState<CandidateKind | 'all'>('all')
  const { setContent } = useContextPanel()
  const workspaceQuery = useProjectWorkspaceQuery(projectSlug)
  const project = workspaceQuery.data?.project ?? null

  const emptyMessage = useMemo(() => {
    if (kindFilter === 'all') {
      return 'No review candidates are waiting for promotion.'
    }
    return `No ${kindLabel(kindFilter)} candidates are waiting for promotion.`
  }, [kindFilter])

  useEffect(() => {
    setContent(
      <div className="space-y-5 p-5">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Review inbox
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            {project?.name ?? projectSlug}
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Promote extracted decisions, requirements, and open questions into curated records from a single review surface.
          </p>
        </div>

        <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Review policy
          </div>
          <div className="mt-3 space-y-2 text-sm text-muted-foreground">
            <div>Sort by confidence or severity before triage.</div>
            <div>Accept creates curated records. Edit &amp; Accept lets you correct the candidate first.</div>
            <div>Reject keeps the candidate out of the cabinet record set.</div>
          </div>
        </div>
      </div>,
    )
    return () => setContent(null)
  }, [project, projectSlug, setContent])

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
              Candidate review
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              Review inbox for {project?.name ?? projectSlug}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
              Triage extracted decisions, requirements, and open questions before they become curated records in the cabinet.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-2 text-xs text-muted-foreground">
              <SlidersHorizontal className="size-3.5" />
              <span>Sort</span>
              <select
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as 'confidence' | 'severity')}
                className="bg-transparent text-foreground outline-none"
              >
                <option value="confidence">Confidence</option>
                <option value="severity">Severity</option>
              </select>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant={kindFilter === 'all' ? 'default' : 'outline'}
                onClick={() => setKindFilter('all')}
              >
                All
              </Button>
              {CANDIDATE_KINDS.map((kind) => (
                <Button
                  key={kind}
                  type="button"
                  size="sm"
                  variant={kindFilter === kind ? 'default' : 'outline'}
                  onClick={() => setKindFilter(kind)}
                >
                  {kindLabel(kind)}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.95fr)]">
        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Inbox className="size-4" />
              Inbox queue
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Pending</div>
                <div className="mt-3 text-3xl font-semibold tracking-tight">0</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Sort mode</div>
                <div className="mt-3 text-lg font-medium capitalize">{sortMode}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Filter</div>
                <div className="mt-3 text-lg font-medium capitalize">
                  {kindFilter === 'all' ? 'All candidates' : kindLabel(kindFilter)}
                </div>
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-dashed border-border/80 bg-background/60 p-6">
              <div className="flex items-start gap-4">
                <div className="rounded-2xl border border-border/70 bg-card/80 p-3">
                  <ShieldAlert className="size-5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold tracking-tight">{emptyMessage}</h3>
                    <Badge variant="outline">Ready for curated promotion</Badge>
                  </div>
                  <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
                    When candidates arrive, each row here will show extraction method badges, confidence, severity, source context, and direct Accept, Edit &amp; Accept, or Reject actions.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle>Review actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">regex</Badge>
                <Badge variant="outline">gliner</Badge>
                <Badge variant="outline">high confidence</Badge>
              </div>
              <div>
                <div className="text-sm font-medium">Candidate action model</div>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">
                  Promotion is explicit. Curated records are only created after an operator accepts or edits and accepts a candidate.
                </div>
              </div>
              <Separator />
              <div className="grid gap-2">
                <Button type="button" className="justify-start" disabled>
                  <Check className="mr-2 size-4" />
                  Accept
                </Button>
                <Button type="button" variant="outline" className="justify-start" disabled>
                  <FilePenLine className="mr-2 size-4" />
                  Edit &amp; Accept
                </Button>
                <Button type="button" variant="outline" className="justify-start" disabled>
                  <X className="mr-2 size-4" />
                  Reject
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
