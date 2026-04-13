import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Check,
  FilePenLine,
  Inbox,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { useContextPanel } from '@/lib/context-panel'
import { api, type Candidate } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

interface ReviewInboxProps {
  projectSlug: string
}

type CandidateKind = Candidate['candidate_type']

const CANDIDATE_KINDS: CandidateKind[] = ['decision', 'requirement', 'open_question']

const METHOD_BADGES: Record<
  string,
  { label: string; variant: 'default' | 'secondary' | 'outline' }
> = {
  structured_adr: { label: 'Parsed from ADR', variant: 'default' },
  regex_req_id: { label: 'REQ-ID match', variant: 'secondary' },
  regex_shall_must: { label: 'Requirement language', variant: 'secondary' },
  regex_question_mark: { label: 'Question marker', variant: 'outline' },
  regex_todo_marker: { label: 'TODO / TBD marker', variant: 'outline' },
  gliner: { label: 'GLiNER extracted', variant: 'outline' },
}

const SEVERITY_ORDER: Record<Candidate['severity'], number> = {
  high: 0,
  medium: 1,
  low: 2,
}

function kindLabel(kind: CandidateKind): string {
  return kind.replace('_', ' ')
}

function severityBadgeVariant(
  severity: Candidate['severity'],
): 'default' | 'secondary' | 'outline' {
  if (severity === 'high') {
    return 'default'
  }
  if (severity === 'medium') {
    return 'secondary'
  }
  return 'outline'
}

function defaultEdits(candidate: Candidate): Record<string, string> {
  return {
    title: candidate.title,
    context: candidate.context ?? '',
    decision: candidate.decision ?? '',
    consequences: candidate.consequences ?? '',
    description: candidate.description ?? '',
    priority: candidate.priority ?? '',
    resolution: candidate.resolution ?? '',
  }
}

export function ReviewInbox({ projectSlug }: ReviewInboxProps) {
  const [sortMode, setSortMode] = useState<'confidence' | 'severity'>('confidence')
  const [kindFilter, setKindFilter] = useState<CandidateKind | 'all'>('all')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [actingId, setActingId] = useState<string | null>(null)
  const { setContent } = useContextPanel()
  const queryClient = useQueryClient()
  const workspaceQuery = useProjectWorkspaceQuery(projectSlug)
  const project = workspaceQuery.data?.project ?? null
  const inboxQuery = useQuery({
    queryKey: queryKeys.inbox(projectSlug),
    queryFn: () => api.inbox.list(projectSlug),
  })
  const candidates = inboxQuery.data ?? []

  const pendingCount = candidates.length
  const highSeverityCount = candidates.filter((candidate) => candidate.severity === 'high').length
  const filteredCandidates = useMemo(() => {
    const visible =
      kindFilter === 'all'
        ? candidates
        : candidates.filter((candidate) => candidate.candidate_type === kindFilter)

    return [...visible].sort((left, right) => {
      if (sortMode === 'severity') {
        return (
          SEVERITY_ORDER[left.severity] - SEVERITY_ORDER[right.severity] ||
          (right.confidence ?? 0) - (left.confidence ?? 0) ||
          left.title.localeCompare(right.title)
        )
      }
      return (
        (right.confidence ?? 0) - (left.confidence ?? 0) ||
        SEVERITY_ORDER[left.severity] - SEVERITY_ORDER[right.severity] ||
        left.title.localeCompare(right.title)
      )
    })
  }, [candidates, kindFilter, sortMode])

  useEffect(() => {
    setContent(
      <div className="space-y-5 p-5">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Candidate review inbox
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            {project?.name ?? projectSlug}
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            AI and deterministic parsers can suggest structured knowledge, but promotion into the
            cabinet stays explicit. Review candidates here before they become curated records.
          </p>
        </div>

        <div className="grid gap-3">
          <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Review policy
            </div>
            <div className="mt-3 space-y-2 text-sm text-muted-foreground">
              <div>Accept promotes as-is into `.piq/records/`.</div>
              <div>Edit &amp; Accept lets you correct titles, context, and structured fields first.</div>
              <div>Reject keeps the item out of the curated record set.</div>
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Queue state
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-muted-foreground">Pending</div>
                <div className="mt-1 font-medium">{pendingCount}</div>
              </div>
              <div>
                <div className="text-muted-foreground">High severity</div>
                <div className="mt-1 font-medium">{highSeverityCount}</div>
              </div>
            </div>
          </div>
        </div>
      </div>,
    )
    return () => setContent(null)
  }, [highSeverityCount, pendingCount, project, projectSlug, setContent])

  const invalidateIntelligence = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.inbox(projectSlug) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.intelligenceSummary(projectSlug) }),
    ])
  }

  const startEditing = (candidate: Candidate) => {
    setEditingId(candidate.id)
    setEdits(defaultEdits(candidate))
  }

  const stopEditing = () => {
    setEditingId(null)
    setEdits({})
  }

  const handleAccept = async (candidate: Candidate, withEdits: boolean) => {
    setActingId(candidate.id)
    try {
      await api.inbox.accept(
        projectSlug,
        candidate.candidate_type,
        candidate.id,
        withEdits ? edits : undefined,
      )
      stopEditing()
      await invalidateIntelligence()
    } catch (error) {
      alert(String(error))
    } finally {
      setActingId(null)
    }
  }

  const handleReject = async (candidate: Candidate) => {
    setActingId(candidate.id)
    try {
      await api.inbox.reject(projectSlug, candidate.candidate_type, candidate.id)
      if (editingId === candidate.id) {
        stopEditing()
      }
      await invalidateIntelligence()
    } catch (error) {
      alert(String(error))
    } finally {
      setActingId(null)
    }
  }

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
              Promote decisions, requirements, and open questions into curated records only after a
              deliberate review step.
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
                <div className="mt-3 text-3xl font-semibold tracking-tight">{pendingCount}</div>
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

            {inboxQuery.isLoading ? (
              <div className="rounded-[1.75rem] border border-dashed border-border/80 bg-background/60 p-6 text-sm text-muted-foreground">
                Loading candidate inbox…
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div className="rounded-[1.75rem] border border-dashed border-border/80 bg-background/60 p-6">
                <div className="flex items-start gap-4">
                  <div className="rounded-2xl border border-border/70 bg-card/80 p-3">
                    <ShieldAlert className="size-5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold tracking-tight">No pending candidates.</h3>
                      <Badge variant="outline">Queue clear</Badge>
                    </div>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
                      New items appear here after documents are ingested and candidate extraction
                      runs.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              filteredCandidates.map((candidate) => {
                const methodInfo = candidate.extraction_method
                  ? METHOD_BADGES[candidate.extraction_method]
                  : null
                const isEditing = editingId === candidate.id
                const isActing = actingId === candidate.id

                return (
                  <Card key={candidate.id} className="bg-background/70">
                    <CardContent className="space-y-4 p-5">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="secondary">{kindLabel(candidate.candidate_type)}</Badge>
                            <Badge variant={severityBadgeVariant(candidate.severity)}>
                              {candidate.severity} severity
                            </Badge>
                            {methodInfo && (
                              <Badge variant={methodInfo.variant}>{methodInfo.label}</Badge>
                            )}
                            {candidate.confidence != null && (
                              <span className="text-xs text-muted-foreground">
                                confidence {(candidate.confidence * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold tracking-tight">{candidate.title}</h3>
                            {candidate.context && (
                              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                                {candidate.context}
                              </p>
                            )}
                          </div>
                          {candidate.source_doc_path && (
                            <div className="text-xs text-muted-foreground">
                              Source: {candidate.source_doc_path}
                              {candidate.source_version != null ? ` v${candidate.source_version}` : ''}
                            </div>
                          )}
                        </div>

                        {candidate.source_doc_path && (
                          <Link
                            to="/projects/$slug/docs/$"
                            params={{ slug: projectSlug, _splat: candidate.source_doc_path }}
                            className="inline-flex h-9 items-center rounded-lg border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
                          >
                            View source
                          </Link>
                        )}
                      </div>

                      {(candidate.decision || candidate.consequences || candidate.description || candidate.priority || candidate.resolution) && (
                        <div className="grid gap-3 md:grid-cols-2">
                          {candidate.decision && (
                            <div className="rounded-xl border border-border/70 bg-card/70 px-3 py-3 text-sm">
                              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Decision
                              </div>
                              <div className="mt-2 whitespace-pre-wrap">{candidate.decision}</div>
                            </div>
                          )}
                          {candidate.consequences && (
                            <div className="rounded-xl border border-border/70 bg-card/70 px-3 py-3 text-sm">
                              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Consequences
                              </div>
                              <div className="mt-2 whitespace-pre-wrap">{candidate.consequences}</div>
                            </div>
                          )}
                          {candidate.description && (
                            <div className="rounded-xl border border-border/70 bg-card/70 px-3 py-3 text-sm">
                              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Description
                              </div>
                              <div className="mt-2 whitespace-pre-wrap">{candidate.description}</div>
                            </div>
                          )}
                          {candidate.priority && (
                            <div className="rounded-xl border border-border/70 bg-card/70 px-3 py-3 text-sm">
                              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Priority
                              </div>
                              <div className="mt-2">{candidate.priority}</div>
                            </div>
                          )}
                          {candidate.resolution && (
                            <div className="rounded-xl border border-border/70 bg-card/70 px-3 py-3 text-sm md:col-span-2">
                              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                Resolution
                              </div>
                              <div className="mt-2 whitespace-pre-wrap">{candidate.resolution}</div>
                            </div>
                          )}
                        </div>
                      )}

                      {isEditing && (
                        <div className="space-y-3 rounded-2xl border border-border/70 bg-card/70 p-4">
                          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                            Edit before promotion
                          </div>
                          <Input
                            value={edits.title ?? ''}
                            onChange={(event) =>
                              setEdits((current) => ({ ...current, title: event.target.value }))
                            }
                            placeholder={candidate.candidate_type === 'open_question' ? 'Question' : 'Title'}
                          />
                          <Textarea
                            value={edits.context ?? ''}
                            onChange={(event) =>
                              setEdits((current) => ({ ...current, context: event.target.value }))
                            }
                            placeholder="Context"
                          />
                          {candidate.candidate_type === 'decision' && (
                            <>
                              <Textarea
                                value={edits.decision ?? ''}
                                onChange={(event) =>
                                  setEdits((current) => ({ ...current, decision: event.target.value }))
                                }
                                placeholder="Decision"
                              />
                              <Textarea
                                value={edits.consequences ?? ''}
                                onChange={(event) =>
                                  setEdits((current) => ({ ...current, consequences: event.target.value }))
                                }
                                placeholder="Consequences"
                              />
                            </>
                          )}
                          {candidate.candidate_type === 'requirement' && (
                            <>
                              <Textarea
                                value={edits.description ?? ''}
                                onChange={(event) =>
                                  setEdits((current) => ({ ...current, description: event.target.value }))
                                }
                                placeholder="Description"
                              />
                              <Input
                                value={edits.priority ?? ''}
                                onChange={(event) =>
                                  setEdits((current) => ({ ...current, priority: event.target.value }))
                                }
                                placeholder="Priority"
                              />
                            </>
                          )}
                          {candidate.candidate_type === 'open_question' && (
                            <Textarea
                              value={edits.resolution ?? ''}
                              onChange={(event) =>
                                setEdits((current) => ({ ...current, resolution: event.target.value }))
                              }
                              placeholder="Resolution (optional)"
                            />
                          )}
                        </div>
                      )}

                      <Separator />

                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          onClick={() => handleAccept(candidate, false)}
                          disabled={isActing}
                        >
                          <Check className="mr-2 size-4" />
                          {isActing ? 'Working…' : 'Promote to curated record'}
                        </Button>
                        {isEditing ? (
                          <>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => handleAccept(candidate, true)}
                              disabled={isActing}
                            >
                              <FilePenLine className="mr-2 size-4" />
                              Save edits &amp; promote
                            </Button>
                            <Button type="button" variant="ghost" onClick={stopEditing} disabled={isActing}>
                              Cancel editing
                            </Button>
                          </>
                        ) : (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => startEditing(candidate)}
                            disabled={isActing}
                          >
                            <FilePenLine className="mr-2 size-4" />
                            Edit &amp; Accept
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => handleReject(candidate)}
                          disabled={isActing}
                        >
                          <X className="mr-2 size-4" />
                          Reject
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })
            )}
          </CardContent>
        </Card>

        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle>Promotion model</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/70 p-4">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">candidate</Badge>
                <Badge variant="outline">human-reviewed</Badge>
                <Badge variant="outline">filesystem-backed</Badge>
              </div>
              <div>
                <div className="text-sm font-medium">Trust transition</div>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">
                  Candidate rows are rebuildable. Promotion writes curated YAML to disk under
                  `.piq/records/`, making the record durable and auditable.
                </div>
              </div>
              <Separator />
              <div className="space-y-2 text-sm text-muted-foreground">
                <div>Accept: writes the record as-is.</div>
                <div>Edit &amp; Accept: writes an operator-corrected record and marks it edited.</div>
                <div>Reject: preserves the source document but blocks promotion.</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
