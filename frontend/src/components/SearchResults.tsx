import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'

import { useContextPanel } from '@/lib/context-panel'
import type { AnswerModeResponse, SearchEntityFacet, SearchResultItem } from '@/lib/api'
import type { SearchMode } from '@/lib/search-route'

interface SearchResultsProps {
  results: SearchResultItem[]
  latencyMs?: number | null
  answer: AnswerModeResponse | null
  query: string
  scopeSummary: string
  projectScope: string | null
  searchMode: SearchMode
  onProjectSelect: (project: string) => void
  entityFacets: SearchEntityFacet[]
  loading: boolean
  streamPhase: 'idle' | 'lexical' | 'reranked' | 'answer_ready'
  semanticEnabled: boolean | null
  rerankApplied: boolean | null
}

function buildCountFacets(values: string[]): Array<{ value: string; count: number }> {
  const counts = new Map<string, number>()
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((left, right) => right.count - left.count || left.value.localeCompare(right.value))
}

function rankBadge(result: SearchResultItem): { label: string; bg: string; text: string } {
  if (result.match_signals.includes('vector')) {
    const pct = Math.round(result.fused_score * 100)
    return { label: `Vector Match (${pct}%)`, bg: 'bg-[#dff0d8]', text: 'text-[#3c763d]' }
  }
  if (result.match_signals.includes('entity')) {
    const pct = Math.round(result.fused_score * 100)
    return { label: `Entity Match (${pct}%)`, bg: 'bg-[#d9edf7]', text: 'text-[#22a5f1]' }
  }
  return { label: 'Keyword Match (BM25)', bg: 'bg-[#f3f6f8]', text: 'text-[#666]' }
}

function accentColor(result: SearchResultItem): string {
  if (result.match_signals.includes('vector')) return 'bg-[#5cb85c]'
  if (result.match_signals.includes('entity')) return 'bg-[#22a5f1]'
  return 'bg-[#e1e8ed]'
}

function provenanceLabel(result: SearchResultItem): string {
  if (result.match_signals.includes('vector')) return 'qwen3_embedder'
  if (result.match_signals.includes('entity')) return 'gliner'
  return 'ParadeDB'
}

function humanizeAnswerError(error: string): string {
  if (/chat\/completions|404 Not Found|Connection refused|ECONNREFUSED|timed out/i.test(error)) {
    return 'Answer synthesis is temporarily unavailable. Ranked retrieval results are still shown below.'
  }
  return error
}

export function SearchResults({
  results,
  latencyMs,
  answer,
  query,
  scopeSummary,
  projectScope,
  onProjectSelect,
  loading,
  streamPhase,
  semanticEnabled,
  rerankApplied,
  entityFacets,
}: SearchResultsProps) {
  const [entityFacet, setEntityFacet] = useState<string | null>(null)
  const { setContent } = useContextPanel()

  useEffect(() => {
    setEntityFacet(null)
  }, [query, projectScope])

  const typeFacets = useMemo(
    () => buildCountFacets(results.map((r) => r.document_type)),
    [results],
  )

  const filteredResults = useMemo(() => {
    if (!entityFacet) return results
    return results.filter((result) =>
      result.entities.some((e) => e.canonical_name === entityFacet),
    )
  }, [results, entityFacet])
  const answerText = answer?.answer?.trim() ?? ''
  const answerError = answer?.error?.trim() ? humanizeAnswerError(answer.error) : ''

  useEffect(() => {
    setContent(
      <div className="flex flex-col gap-[10px] p-[16px]">
        <span className="text-[11px] font-semibold text-[#666]">CONTEXT: SEARCH</span>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">FILTERS</span>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Scope</span>
          <span className="font-medium text-[#22a5f1]">{projectScope ?? 'All'}</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Time</span>
          <span className="font-medium text-[#22a5f1]">All</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Doc Type</span>
          <span className="font-medium text-[#22a5f1]">Any</span>
        </div>
        <div className="flex items-start justify-between text-[10px]">
          <span className="text-[#666]">Status</span>
          <span className="font-medium text-[#22a5f1]">Any</span>
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">INTELLIGENCE FACETS</span>
        {typeFacets.map((facet) => (
          <div key={facet.value} className="flex items-center gap-[8px]">
            <div className="size-[12px] rounded-[2px] border border-[#e1e8ed]" />
            <span className="text-[10px] text-[#333]">
              {facet.value.charAt(0).toUpperCase() + facet.value.slice(1).replace('_', ' ')}s (
              {facet.count})
            </span>
          </div>
        ))}
        {entityFacets.length > 0 && <div className="h-px w-full bg-[#e1e8ed]" />}
        {entityFacets.map((facet) => (
          <div
            key={`${facet.entity_type}:${facet.canonical_name}`}
            className="flex items-center gap-[8px]"
          >
            <button
              type="button"
              onClick={() =>
                setEntityFacet((cur) =>
                  cur === facet.canonical_name ? null : facet.canonical_name,
                )
              }
              className={`size-[12px] rounded-[2px] border ${
                entityFacet === facet.canonical_name
                  ? 'border-[#22a5f1] bg-[#22a5f1]'
                  : 'border-[#e1e8ed]'
              }`}
            />
            <span className="text-[10px] text-[#333]">
              {facet.entity_type}: &lsquo;{facet.canonical_name}&rsquo; ({facet.count})
            </span>
          </div>
        ))}
        <div className="h-px w-full bg-[#e1e8ed]" />

        <span className="text-[11px] font-semibold text-[#666]">SEARCH OBSERVABILITY</span>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-[6px]">
            <div
              className={`size-[8px] rounded-full ${rerankApplied !== false ? 'bg-[#5cb85c]' : 'bg-[#999]'}`}
            />
            <span className="text-[10px] text-[#666]">Reranker</span>
          </div>
          <span className="text-[10px] font-medium text-[#22a5f1]">
            {rerankApplied !== false ? 'Qwen3-0.6B' : 'Unavailable'}
          </span>
        </div>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-[6px]">
            <div className="size-[8px] rounded-full bg-[#5cb85c]" />
            <span className="text-[10px] text-[#666]">Latency</span>
          </div>
          <span className="text-[10px] font-medium text-[#333]">
            {latencyMs != null ? `${latencyMs}ms` : '\u2014'}
          </span>
        </div>
        <button
          type="button"
          className="rounded-[4px] border border-[#e1e8ed] bg-white px-[10px] py-[5px] text-[9px] font-semibold text-[#333]"
        >
          GOLD QUERIES: RUN EVAL
        </button>
      </div>,
    )
    return () => setContent(null)
  }, [setContent, projectScope, typeFacets, entityFacets, entityFacet, latencyMs, rerankApplied])

  if (results.length === 0) {
    return (
      <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[14px] text-[11px] text-[#666]">
        No results found for &ldquo;{query}&rdquo; within {scopeSummary}.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[14px]">
      <div className="flex items-center justify-between">
        <h1 className="text-[18px] font-semibold text-[#1b2431]">
          Search: &ldquo;{query}&rdquo;
        </h1>
        <span className="whitespace-pre text-[10px] text-[#666]">
          Showing Top {results.length} Chunks {'  |  '}
          {filteredResults.length > 0
            ? `1 \u2013 ${filteredResults.length} of ${results.length}`
            : `0 of ${results.length}`}
        </span>
      </div>

      {answer && (answerText || answerError) && (
        <div className="flex h-[100px] items-start overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white">
          <div className="h-full w-[4px] shrink-0 bg-[#d9534f]" />
          <div className="flex min-w-0 flex-1 flex-col gap-[8px] px-[16px] py-[14px]">
            <span className="text-[9px] font-semibold text-[#666]">AI SYNTHESIS</span>
            {answerError ? (
              <p className="line-clamp-2 text-[12px] text-[#666]">{answerError}</p>
            ) : (
              <p className="line-clamp-2 text-[12px] text-[#333]">{answerText}</p>
            )}
            {!answerError && answer.citations.length > 0 && (
              <div className="flex items-start gap-[6px] text-[10px]">
                <span className="text-[#666]">Citations:</span>
                {answer.citations.map((citation) => (
                  <Link
                    key={`${citation.index}:${citation.source_ref.chunk_id}`}
                    to="/projects/$slug/docs/$"
                    params={{
                      slug: citation.source_ref.project_slug,
                      _splat: citation.source_ref.canonical_path,
                    }}
                    className="font-medium text-[#22a5f1] hover:underline"
                  >
                    [{citation.human_readable}]
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {loading && streamPhase === 'idle' && (
        <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[14px] text-[11px] text-[#666]">
          Searching&hellip;
        </div>
      )}

      {filteredResults.map((result, index) => {
        const badge = rankBadge(result)
        const accent = accentColor(result)
        const prov = provenanceLabel(result)

        return (
          <div
            key={
              result.chunk_id ||
              `${result.project_slug}:${result.document_path}:${result.version_number}`
            }
            className="flex h-[100px] items-start overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white"
          >
            <div className={`h-[80px] w-[4px] shrink-0 ${accent}`} />
            <div className="flex min-w-0 flex-1 flex-col gap-[4px] px-[16px] py-[12px]">
              <div className="flex items-center gap-[8px] text-[12px] font-semibold">
                <span className="text-[#333]">{index + 1}.</span>
                <Link
                  to="/projects/$slug/docs/$"
                  params={{ slug: result.project_slug, _splat: result.document_path }}
                  search={{
                    sourceQuery: query,
                    sourceSnippet: result.snippet,
                    sourceHeading: result.heading_path,
                    sourceSignals: result.match_signals.join(','),
                  }}
                  className="truncate text-[#22a5f1] hover:underline"
                >
                  {result.document_title}
                </Link>
              </div>
              {result.heading_path && (
                <p className="text-[10px] text-[#666]">
                  {'\u25b8'} {result.heading_path}
                </p>
              )}
              <div className="flex items-start gap-[8px]">
                <span className="text-[10px] text-[#666]">Rank:</span>
                <span
                  className={`rounded-[3px] px-[8px] py-[3px] text-[9px] font-semibold ${badge.bg} ${badge.text}`}
                >
                  {badge.label}
                </span>
                <span className="text-[10px] text-[#666]">Provenance:</span>
                <span className="text-[10px] font-medium text-[#22a5f1]">{prov}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
