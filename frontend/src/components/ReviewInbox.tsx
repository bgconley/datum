import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useContextPanel } from '@/lib/context-panel'
import { api, type Candidate } from '@/lib/api'
import { notify } from '@/lib/notifications'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

interface ReviewInboxProps {
  projectSlug: string
}

const SEVERITY_ORDER: Record<Candidate['severity'], number> = {
  high: 0,
  medium: 1,
  low: 2,
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

function trustText(candidate: Candidate): string {
  if (candidate.extraction_method === 'structured_adr') return 'Trust: Deterministic parser'
  if (candidate.confidence != null) {
    const pct = Math.round(candidate.confidence * 100)
    const level = pct >= 70 ? 'High' : pct >= 40 ? 'Review' : 'Low'
    return `Trust: Conf: ${pct}% (${level})`
  }
  return 'Trust: Unknown'
}

function trustDotColor(candidate: Candidate): string {
  if (candidate.extraction_method === 'structured_adr') return 'bg-[#5cb85c]'
  if (candidate.confidence != null) {
    if (candidate.confidence >= 0.7) return 'bg-[#5cb85c]'
    if (candidate.confidence >= 0.4) return 'bg-[#f0ad4e]'
  }
  return 'bg-[#999]'
}

function sourceText(candidate: Candidate): string {
  const parts: string[] = []
  if (candidate.source_doc_path) {
    let s = candidate.source_doc_path
    if (candidate.source_version != null)
      s += ` v${String(candidate.source_version).padStart(3, '0')}`
    parts.push(s)
  }
  if (candidate.extraction_method && candidate.extraction_method !== 'structured_adr') {
    parts.push(candidate.extraction_method)
  }
  return parts.length > 0 ? `Source: ${parts.join(' \u00b7 ')}` : ''
}

export function ReviewInbox({ projectSlug }: ReviewInboxProps) {
  const [sortMode, setSortMode] = useState<'confidence' | 'severity'>('confidence')
  const [selectedId, setSelectedId] = useState<string | null>(null)
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

  const filteredCandidates = useMemo(() => {
    return [...candidates].sort((left, right) => {
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
  }, [candidates, sortMode])

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
      if (editingId === candidate.id) stopEditing()
      await invalidateIntelligence()
    } catch (error) {
      notify(String(error))
    } finally {
      setActingId(null)
    }
  }

  // Stable ref so context panel buttons always call latest handlers
  const handlersRef = useRef({ handleAccept, handleReject, startEditing })
  handlersRef.current = { handleAccept, handleReject, startEditing }

  useEffect(() => {
    const sel = selectedId ? candidates.find((c) => c.id === selectedId) ?? null : null
    const isEditingSel = sel != null && editingId === sel.id
    const busy = actingId != null

    setContent(
      <div className="flex flex-col gap-[10px]">
        <span className="text-[11px] font-semibold text-[#666]">CONTEXT: INBOX</span>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Scope</span>
          <span className="font-medium text-[#22a5f1]">{project?.name ?? projectSlug}</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Mode</span>
          <span className="font-medium text-[#333]">Active Project</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">CURATION METRICS</span>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#333]">Curated this week</span>
          <span className="font-semibold text-[#5cb85c]">{'\u2014'}</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#333]">AI Acceptance rate</span>
          <span className="font-semibold text-[#5cb85c]">{'\u2014'}</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#333]">Rejected this week</span>
          <span className="font-semibold text-[#d9534f]">{'\u2014'}</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">INGESTION PIPELINE</span>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Jobs queued</span>
          <span className="font-medium text-[#333]">0</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Jobs running</span>
          <span className="font-medium text-[#333]">0</span>
        </div>
        <div className="flex items-start gap-[8px]">
          <div className="rounded-[4px] border border-[#d9534f] bg-white px-[10px] py-[5px]">
            <span className="text-[9px] font-semibold text-[#d9534f]">PAUSE</span>
          </div>
          <span className="text-[10px] font-medium text-[#22a5f1]">qwen3_embedder</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">REVIEW ACTIONS</span>
        <div className="flex items-center gap-[6px]">
          <div className="size-[12px] rounded-[2px] border border-[#e1e8ed]" />
          <span className="text-[10px] text-[#666]">Show .piq/</span>
        </div>
        <div className="flex items-center gap-[6px]">
          <div className="size-[12px] rounded-[2px] border border-[#e1e8ed]" />
          <span className="text-[10px] text-[#666]">Show Deleted</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <div className="flex items-start gap-[8px]">
          <button
            type="button"
            onClick={() => sel && handlersRef.current.handleAccept(sel, isEditingSel)}
            disabled={!sel || busy}
            className="rounded-[4px] bg-[#5cb85c] px-[14px] py-[8px] text-[10px] font-semibold text-white disabled:opacity-40"
          >
            ACCEPT
          </button>
          <button
            type="button"
            onClick={() => {
              if (!sel) return
              if (isEditingSel) handlersRef.current.handleAccept(sel, true)
              else handlersRef.current.startEditing(sel)
            }}
            disabled={!sel || busy}
            className="rounded-[4px] border border-[#e1e8ed] bg-white px-[14px] py-[8px] text-[10px] font-semibold text-[#333] disabled:opacity-40"
          >
            EDIT
          </button>
          <button
            type="button"
            onClick={() => sel && handlersRef.current.handleReject(sel)}
            disabled={!sel || busy}
            className="rounded-[4px] bg-[#d9534f] px-[14px] py-[8px] text-[10px] font-semibold text-white disabled:opacity-40"
          >
            REJECT
          </button>
        </div>
      </div>,
    )
    return () => setContent(null)
  }, [setContent, project, projectSlug, selectedId, candidates, editingId, actingId])

  return (
    <div className="flex flex-col gap-[12px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[12px]">
          <h1 className="text-[18px] font-semibold text-[#1b2431]">Inbox: Candidate Review</h1>
          <span className="text-[13px] text-[#22a5f1]">{project?.name ?? projectSlug}</span>
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
            {filteredCandidates.length > 0
              ? `1 \u2013 ${filteredCandidates.length} of ${candidates.length}`
              : `0 of ${candidates.length}`}
          </span>
        </div>
      </div>

      {inboxQuery.isLoading ? (
        <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[14px] text-[11px] text-[#666]">
          Loading candidate inbox&hellip;
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[14px] text-[11px] text-[#666]">
          No pending candidates. New items appear after document ingestion.
        </div>
      ) : (
        filteredCandidates.map((candidate) => {
          const isEditing = editingId === candidate.id
          const isSelected = selectedId === candidate.id
          const accent =
            candidate.candidate_type === 'decision'
              ? 'bg-[#d9534f]'
              : candidate.candidate_type === 'open_question'
                ? 'bg-[#22a5f1]'
                : 'bg-[#e1e8ed]'
          const isStructuredAdr = candidate.extraction_method === 'structured_adr'
          const isAiCandidate = candidate.extraction_method === 'gliner'

          return (
            <div key={candidate.id}>
              <div
                className={`flex h-[100px] items-start overflow-hidden rounded-[4px] border bg-white ${
                  isSelected ? 'border-[#22a5f1]' : 'border-[#e1e8ed]'
                }`}
              >
                <div className={`h-full w-[4px] shrink-0 ${accent}`} />
                <button
                  type="button"
                  onClick={() => setSelectedId(isSelected ? null : candidate.id)}
                  className="flex h-full w-[40px] shrink-0 items-center justify-center"
                >
                  <div
                    className={`size-[14px] rounded-[2px] border ${
                      isSelected ? 'border-[#22a5f1] bg-[#22a5f1]' : 'border-[#e1e8ed]'
                    }`}
                  >
                    {isSelected && (
                      <svg viewBox="0 0 14 14" className="size-[14px] text-white">
                        <path
                          d="M3 7l3 3 5-5"
                          stroke="currentColor"
                          strokeWidth="2"
                          fill="none"
                        />
                      </svg>
                    )}
                  </div>
                </button>
                <div className="flex min-w-0 flex-1 flex-col gap-[6px] py-[14px] pl-[4px] pr-[16px]">
                  <div className="flex items-center gap-[8px]">
                    <span className="text-[9px] font-semibold text-[#666]">
                      {candidate.candidate_type.replace('_', ' ').toUpperCase()}
                    </span>
                    {isStructuredAdr && (
                      <span className="rounded-[3px] bg-[#d9edf7] px-[8px] py-[3px] text-[9px] font-semibold text-[#22a5f1]">
                        Parsed ADR
                      </span>
                    )}
                    {isAiCandidate && (
                      <span className="rounded-[3px] bg-[#fcf8e3] px-[8px] py-[3px] text-[9px] font-semibold text-[#8a6d3b]">
                        AI Candidate
                      </span>
                    )}
                    {!isStructuredAdr && !isAiCandidate && candidate.extraction_method && (
                      <span className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[9px] font-semibold text-[#333]">
                        {candidate.extraction_method}
                      </span>
                    )}
                  </div>
                  {candidate.source_doc_path ? (
                    <Link
                      to="/projects/$slug/docs/$"
                      params={{ slug: projectSlug, _splat: candidate.source_doc_path }}
                      className="truncate text-[13px] font-semibold text-[#22a5f1] hover:underline"
                    >
                      {candidate.title}
                    </Link>
                  ) : (
                    <p className="truncate text-[13px] font-semibold text-[#22a5f1]">
                      {candidate.title}
                    </p>
                  )}
                  <div className="flex items-center gap-[8px]">
                    <div
                      className={`size-[8px] shrink-0 rounded-full ${trustDotColor(candidate)}`}
                    />
                    <span className="text-[10px] text-[#333]">{trustText(candidate)}</span>
                    {sourceText(candidate) && (
                      <>
                        <span className="text-[10px] text-[#999]">{'\u00b7'}</span>
                        <span className="truncate text-[10px] text-[#666]">
                          {sourceText(candidate)}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {isEditing && (
                <div className="mt-[4px] rounded-[4px] border border-[#e1e8ed] bg-white p-[16px]">
                  <div className="mb-[10px] text-[9px] font-semibold text-[#666]">
                    EDIT BEFORE PROMOTION
                  </div>
                  <div className="flex flex-col gap-[8px]">
                    <Input
                      value={edits.title ?? ''}
                      onChange={(e) => setEdits((prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="Title"
                      className="text-[11px]"
                    />
                    <Textarea
                      value={edits.context ?? ''}
                      onChange={(e) => setEdits((prev) => ({ ...prev, context: e.target.value }))}
                      placeholder="Context"
                      className="text-[11px]"
                    />
                    {candidate.candidate_type === 'decision' && (
                      <>
                        <Textarea
                          value={edits.decision ?? ''}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, decision: e.target.value }))
                          }
                          placeholder="Decision"
                          className="text-[11px]"
                        />
                        <Textarea
                          value={edits.consequences ?? ''}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, consequences: e.target.value }))
                          }
                          placeholder="Consequences"
                          className="text-[11px]"
                        />
                      </>
                    )}
                    {candidate.candidate_type === 'requirement' && (
                      <>
                        <Textarea
                          value={edits.description ?? ''}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, description: e.target.value }))
                          }
                          placeholder="Description"
                          className="text-[11px]"
                        />
                        <Input
                          value={edits.priority ?? ''}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, priority: e.target.value }))
                          }
                          placeholder="Priority"
                          className="text-[11px]"
                        />
                      </>
                    )}
                    {candidate.candidate_type === 'open_question' && (
                      <Textarea
                        value={edits.resolution ?? ''}
                        onChange={(e) =>
                          setEdits((prev) => ({ ...prev, resolution: e.target.value }))
                        }
                        placeholder="Resolution (optional)"
                        className="text-[11px]"
                      />
                    )}
                    <div className="flex items-center gap-[8px]">
                      <button
                        type="button"
                        onClick={() => handleAccept(candidate, true)}
                        disabled={actingId != null}
                        className="rounded-[4px] bg-[#5cb85c] px-[14px] py-[8px] text-[10px] font-semibold text-white disabled:opacity-40"
                      >
                        SAVE &amp; PROMOTE
                      </button>
                      <button
                        type="button"
                        onClick={stopEditing}
                        className="rounded-[4px] border border-[#e1e8ed] bg-white px-[14px] py-[8px] text-[10px] font-semibold text-[#333]"
                      >
                        CANCEL
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
