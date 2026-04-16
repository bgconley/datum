import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Badge } from '@/components/ui/badge'
import { useContextPanel } from '@/lib/context-panel'
import { api, type Candidate } from '@/lib/api'
import { notify } from '@/lib/notifications'
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
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Context: Inbox
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
          <div className="rounded border border-border bg-muted p-4">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Review policy
            </div>
            <div className="mt-3 space-y-2 text-sm text-muted-foreground">
              <div>Accept promotes as-is into `.piq/records/`.</div>
              <div>Edit &amp; Accept lets you correct titles, context, and structured fields first.</div>
              <div>Reject keeps the item out of the curated record set.</div>
            </div>
          </div>
          <div className="rounded border border-border bg-muted p-4">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
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
      notify(String(error))
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
      notify(String(error))
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-[12px] overflow-auto px-[24px] py-[20px]">
      {/* Title row — Figma: Inbox: Candidate Review + project + sort + count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[12px]">
          <span className="text-[18px] font-semibold text-[#1b2431]">
            Inbox: Candidate Review
          </span>
          <span className="text-[13px] text-[#22a5f1]">
            {project?.name ?? projectSlug}
          </span>
        </div>
        <div className="flex items-center gap-[8px]">
          <span className="text-[10px] text-[#666]">Sorted by:</span>
          <button
            type="button"
            onClick={() => setSortMode('confidence')}
            className={`rounded-[4px] border border-[#e1e8ed] px-[10px] py-[5px] text-[9px] font-semibold ${
              sortMode === 'confidence' ? 'bg-[#333] text-white' : 'bg-white text-[#333]'
            }`}
          >
            CONF.
          </button>
          <button
            type="button"
            onClick={() => setSortMode('severity')}
            className={`rounded-[4px] border border-[#e1e8ed] px-[10px] py-[5px] text-[9px] font-semibold ${
              sortMode === 'severity' ? 'bg-[#333] text-white' : 'bg-white text-[#333]'
            }`}
          >
            SEVERITY
          </button>
          <span className="text-[10px] text-[#666]">
            1 - {filteredCandidates.length} of {filteredCandidates.length}
          </span>
        </div>
      </div>

      {/* Candidate cards — flat list matching Figma */}
      <div className="flex flex-col gap-[12px]">
            {inboxQuery.isLoading ? (
              <div className="rounded-[4px] border border-[#e1e8ed] bg-white p-[24px] text-[12px] text-[#999]">
                Loading candidate inbox…
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div className="rounded-[4px] border border-[#e1e8ed] bg-white p-[24px]">
                <div className="flex items-start gap-4">
                  <div>
                    <h3 className="text-[13px] font-semibold text-[#333]">No pending candidates.</h3>
                    <p className="mt-2 text-[11px] text-[#999]">
                      New items appear here after documents are ingested and candidate extraction runs.
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

                const cardAccent = candidate.candidate_type === 'decision'
                  ? 'border-l-4 border-l-destructive'
                  : candidate.candidate_type === 'requirement'
                    ? 'border-l-4 border-l-amber-500'
                    : 'border-l-4 border-l-primary'

                const isStructuredAdr = candidate.extraction_method === 'structured_adr'
                const isGliner = candidate.extraction_method === 'gliner'

                const confidenceDotColor = candidate.confidence != null
                  ? candidate.confidence >= 0.7
                    ? 'bg-green-500'
                    : candidate.confidence >= 0.4
                      ? 'bg-amber-500'
                      : 'bg-gray-400'
                  : null

                const accentColor = candidate.candidate_type === 'decision'
                  ? 'bg-[#d9534f]'
                  : 'bg-[#e1e8ed]'

                return (
                  <div key={candidate.id} className="flex overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white">
                    {/* Left accent bar */}
                    <div className={`w-[4px] shrink-0 ${accentColor}`} />
                    {/* Content */}
                    <div className="flex flex-1 flex-col gap-[6px] px-[16px] py-[14px]">
                      <div className="flex items-center gap-[8px]">
                        <span className="text-[9px] font-semibold text-[#666]">
                          {kindLabel(candidate.candidate_type).toUpperCase()}
                        </span>
                        {isStructuredAdr && (
                          <span className="rounded-[3px] bg-[#d9edf7] px-[8px] py-[3px] text-[9px] font-semibold text-[#22a5f1]">
                            Parsed ADR
                          </span>
                        )}
                        {isGliner && (
                          <span className="rounded-[3px] bg-[#fcf8e3] px-[8px] py-[3px] text-[9px] font-semibold text-[#8a6d3b]">
                            AI Candidate
                          </span>
                        )}
                        {!isStructuredAdr && !isGliner && methodInfo && (
                          <span className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[9px] font-semibold text-[#333]">
                            {methodInfo.label}
                          </span>
                        )}
                      </div>
                      <h3 className="text-[13px] font-semibold text-[#22a5f1]">{candidate.title}</h3>
                      <div className="flex items-center gap-[8px]">
                        {confidenceDotColor && (
                          <span className={`inline-block size-[8px] rounded-full ${confidenceDotColor}`} />
                        )}
                        <span className="text-[10px] text-[#333]">
                          Trust: {isStructuredAdr ? 'Deterministic parser' : candidate.confidence != null ? `Conf: ${(candidate.confidence * 100).toFixed(0)}%` : 'Unknown'}
                        </span>
                        <span className="text-[10px] text-[#999]">·</span>
                        <span className="text-[10px] text-[#666]">
                          Source: {candidate.source_doc_path ?? 'unknown'}
                          {candidate.source_version != null ? ` v${String(candidate.source_version).padStart(3, '0')}` : ''}
                          {candidate.extraction_method ? ` · ${candidate.extraction_method}` : ''}
                        </span>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center p-[14px]">
                        {candidate.source_doc_path && (
                          <Link
                            to="/projects/$slug/docs/$"
                            params={{ slug: projectSlug, _splat: candidate.source_doc_path }}
                            className="text-[10px] text-[#22a5f1] hover:underline"
                          >
                            View source
                          </Link>
                        )}
                      </div>
                  </div>

                )
              })
            )}
        </div>
      </div>
    </div>
  )
}
