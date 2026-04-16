import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

function describePhase(
  loading: boolean,
  streamPhase: 'idle' | 'lexical' | 'reranked' | 'answer_ready',
  semanticEnabled: boolean | null,
  rerankApplied: boolean | null,
  answer: AnswerModeResponse | null,
): string | null {
  if (!loading && streamPhase === 'answer_ready') {
    if (answer?.error) {
      return 'Search results are ready, but grounded answer synthesis was unavailable for this query.'
    }
    if (answer?.citations.length) {
      return 'Final results are ready and answer synthesis completed with citations.'
    }
    return 'Final results are ready and answer synthesis completed.'
  }

  if (loading && streamPhase === 'lexical') {
    return semanticEnabled === false
      ? 'Lexical results are ready. Semantic search is unavailable, so the final pass will confirm exact-term and keyword ranking.'
      : 'Lexical results are ready. Running semantic fusion and cross-encoder reranking now.'
  }

  if (loading) {
    return 'Searching lexical, exact-term, semantic, and reranking stages.'
  }

  if (streamPhase === 'reranked' && semanticEnabled === false) {
    return 'Final results were produced without semantic vectors because the embedding service was unavailable.'
  }

  if (streamPhase === 'reranked' && rerankApplied === false) {
    return 'Results reflect lexical, exact-term, and semantic fusion. Reranking was unavailable, so fused order was preserved.'
  }

  if (streamPhase === 'reranked') {
    return 'Final results combine lexical, exact-term, semantic, and reranking signals.'
  }

  return null
}

export function SearchResults({
  results,
  latencyMs,
  answer,
  query,
  scopeSummary,
  projectScope,
  searchMode,
  onProjectSelect,
  loading,
  streamPhase,
  semanticEnabled,
  rerankApplied,
  entityFacets,
}: SearchResultsProps) {
  const [signalFacet, setSignalFacet] = useState<string | null>(null)
  const [termFacet, setTermFacet] = useState<string | null>(null)
  const [entityFacet, setEntityFacet] = useState<string | null>(null)

  useEffect(() => {
    setSignalFacet(null)
    setTermFacet(null)
    setEntityFacet(null)
  }, [query, projectScope, searchMode])

  const modeFilteredResults = useMemo(() => results, [results])

  const projectFacets = buildCountFacets(modeFilteredResults.map((result) => result.project_slug)).map(
    ({ value, count }) => ({
      value,
      count,
    }),
  )
  const signalFacets = buildCountFacets(modeFilteredResults.flatMap((result) => result.match_signals))
  const termFacets = buildCountFacets(modeFilteredResults.flatMap((result) => result.matched_terms)).slice(0, 10)
  const typeFacets = buildCountFacets(modeFilteredResults.map((result) => result.document_type))
  const phaseDescription = describePhase(
    loading,
    streamPhase,
    semanticEnabled,
    rerankApplied,
    answer,
  )

  const filteredResults = modeFilteredResults.filter((result) => {
    if (signalFacet && !result.match_signals.includes(signalFacet)) {
      return false
    }
    if (termFacet && !result.matched_terms.includes(termFacet)) {
      return false
    }
    if (
      entityFacet &&
      !result.entities.some((entity) => entity.canonical_name === entityFacet)
    ) {
      return false
    }
    return true
  })

  if (modeFilteredResults.length === 0) {
    return (
      <div className="rounded border border-dashed border-border bg-white px-6 py-10 text-center text-sm text-muted-foreground">
        No results found for "{query}" within {scopeSummary}.
      </div>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="space-y-4">
        {answer && (answer.answer || answer.error) && (
          <Card className="border-l-4 border-l-destructive bg-white">
            <CardHeader>
              <CardTitle className="text-base">
                {answer.error ? 'Grounded answer unavailable' : 'AI Synthesis'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {answer.error ? (
                <div className="rounded border border-border bg-background px-3 py-3 text-muted-foreground">
                  {answer.error}
                </div>
              ) : (
                <>
                  <div className="whitespace-pre-wrap leading-7">{answer.answer}</div>
                  {answer.citations.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Citations
                      </div>
                      <div className="space-y-2">
                        {answer.citations.map((citation) => (
                          <Link
                            key={`${citation.index}:${citation.source_ref.chunk_id}`}
                            to="/projects/$slug/docs/$"
                            params={{
                              slug: citation.source_ref.project_slug,
                              _splat: citation.source_ref.canonical_path,
                            }}
                            search={{
                              query: query,
                              sourceQueryLabel: 'Answer',
                              sourceSnippet: citation.human_readable,
                              sourceVersion: citation.source_ref.version_number,
                              sourceStart: citation.source_ref.line_start,
                              sourceEnd: citation.source_ref.line_end,
                              sourceChunkId: citation.source_ref.chunk_id,
                            }}
                            className="block rounded border border-border bg-background px-3 py-2 text-primary transition-colors hover:bg-muted"
                          >
                            [{citation.index}] {citation.human_readable}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                  {answer.model && (
                    <div className="text-xs text-muted-foreground">Model: {answer.model}</div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}
        <Card className="bg-white">
          <CardHeader>
            <CardTitle className="text-base">Facets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {!projectScope && projectFacets.length > 1 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Projects
                </div>
                <div className="flex flex-wrap gap-2">
                  {projectFacets.map((facet) => (
                    <Button
                      key={facet.value}
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={() => onProjectSelect(facet.value)}
                    >
                      {facet.value} ({facet.count})
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {typeFacets.length > 1 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Doc types
                </div>
                <div className="flex flex-wrap gap-2">
                  {typeFacets.map((facet) => (
                    <Badge key={facet.value} variant="outline">
                      {facet.value} ({facet.count})
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {signalFacets.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Signals
                </div>
                <div className="flex flex-wrap gap-2">
                  {signalFacets.map((facet) => (
                    <Button
                      key={facet.value}
                      type="button"
                      variant={signalFacet === facet.value ? 'secondary' : 'outline'}
                      size="xs"
                      onClick={() => setSignalFacet(signalFacet === facet.value ? null : facet.value)}
                    >
                      {facet.value} ({facet.count})
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {termFacets.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Exact terms
                </div>
                <div className="flex flex-wrap gap-2">
                  {termFacets.map((facet) => (
                    <Button
                      key={facet.value}
                      type="button"
                      variant={termFacet === facet.value ? 'secondary' : 'outline'}
                      size="xs"
                      onClick={() => setTermFacet(termFacet === facet.value ? null : facet.value)}
                    >
                      {facet.value}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {entityFacets.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Entities
                </div>
                <div className="flex flex-wrap gap-2">
                  {entityFacets.map((facet) => (
                    <Button
                      key={`${facet.entity_type}:${facet.canonical_name}`}
                      type="button"
                      variant={entityFacet === facet.canonical_name ? 'secondary' : 'outline'}
                      size="xs"
                      onClick={() =>
                        setEntityFacet(
                          entityFacet === facet.canonical_name ? null : facet.canonical_name,
                        )
                      }
                    >
                      {facet.canonical_name} ({facet.count})
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {(projectScope || signalFacet || termFacet || entityFacet) && (
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={() => {
                  if (projectScope) {
                    onProjectSelect('')
                  }
                  setSignalFacet(null)
                  setTermFacet(null)
                  setEntityFacet(null)
                }}
              >
                Clear facets
              </Button>
            )}
          </CardContent>
        </Card>
      </aside>

      <div className="space-y-4">
        <div className="rounded border border-border bg-white p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <div className="text-sm font-medium text-foreground">
                {filteredResults.length} visible result{filteredResults.length === 1 ? '' : 's'} for "{query}"
                {filteredResults.length !== modeFilteredResults.length ? ` (${modeFilteredResults.length} total)` : ''}
              </div>
              <div className="text-sm text-muted-foreground">
                {loading ? 'Searching' : 'Across'} {scopeSummary}
                {latencyMs != null ? ` in ${latencyMs}ms` : ''}
              </div>
            </div>
            {phaseDescription && (
              <div className="rounded border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                {phaseDescription}
              </div>
            )}
          </div>
        </div>

        {filteredResults.map((result) => {
          const accentClass = result.match_signals.includes('vector')
            ? 'border-l-4 border-l-green-500'
            : result.match_signals.includes('entity')
              ? 'border-l-4 border-l-primary'
              : 'border-l-4 border-l-gray-400'

          return (
            <Card key={result.chunk_id || `${result.project_slug}:${result.document_path}:${result.version_number}`} className={`border border-border bg-white ${accentClass}`}>
              <CardHeader>
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <CardTitle className="truncate">{result.document_title}</CardTitle>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {result.project_slug} / {result.document_path}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="outline">{result.document_type}</Badge>
                    <Badge variant="outline">v{result.version_number}</Badge>
                    {(result.line_start > 0 || result.line_end > 0) && (
                      <Badge variant="outline">
                        lines {result.line_start}-{result.line_end}
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-1.5">
                  {result.match_signals.map((signal) => {
                    const signalColor = signal === 'vector'
                      ? 'bg-green-100 text-green-800'
                      : signal === 'entity'
                        ? 'bg-primary/10 text-primary'
                        : 'bg-muted text-muted-foreground'
                    return (
                      <span key={signal} className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${signalColor}`}>
                        {signal}
                      </span>
                    )
                  })}
                  {result.heading_path && (
                    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {result.heading_path}
                    </span>
                  )}
                </div>

                <p className="text-sm leading-6 text-foreground">{result.snippet}</p>

                {result.matched_terms.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {result.matched_terms.map((term) => (
                      <Badge key={term} variant="secondary" className="text-xs">
                        {term}
                      </Badge>
                    ))}
                  </div>
                )}

                {result.entities.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {result.entities.map((entity) => (
                      <Badge
                        key={`${entity.entity_type}:${entity.canonical_name}`}
                        variant="outline"
                        className="text-xs"
                      >
                        {entity.canonical_name}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    to="/projects/$slug/docs/$"
                    params={{ slug: result.project_slug, _splat: result.document_path }}
                    search={{
                      sourceQuery: query,
                      sourceSnippet: result.snippet,
                      sourceHeading: result.heading_path,
                      sourceSignals: result.match_signals.join(','),
                    }}
                    className="inline-flex h-8 items-center rounded border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
                  >
                    Open source
                  </Link>

                  <details className="text-sm">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      Why this result?
                    </summary>
                    <div className="mt-3 rounded border border-border bg-background p-4">
                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Matched signals
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {result.match_signals.map((signal) => (
                              <Badge key={signal} variant="secondary">
                                {signal}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Exact terms
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {result.matched_terms.length > 0 ? (
                              result.matched_terms.map((term) => (
                                <Badge key={term} variant="outline">
                                  {term}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-sm text-muted-foreground">No exact-term matches surfaced.</span>
                            )}
                          </div>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Entities
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {result.entities.length > 0 ? (
                              result.entities.map((entity) => (
                                <Badge
                                  key={`${entity.entity_type}:${entity.canonical_name}`}
                                  variant="outline"
                                >
                                  {entity.canonical_name}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-sm text-muted-foreground">
                                No entities surfaced from this chunk.
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-3">
                        <div className="rounded border border-border bg-white px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Heading path</div>
                          <div className="mt-1">{result.heading_path || 'Top-level chunk'}</div>
                        </div>
                        <div className="rounded border border-border bg-white px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Document status</div>
                          <div className="mt-1">{result.document_status}</div>
                        </div>
                        <div className="rounded border border-border bg-white px-3 py-2 text-xs">
                          <div className="text-muted-foreground">Fused score</div>
                          <div className="mt-1">{result.fused_score.toFixed(4)}</div>
                        </div>
                      </div>
                    </div>
                  </details>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
