import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SearchResultItem } from '@/lib/api'

interface SearchResultsProps {
  results: SearchResultItem[]
  latencyMs?: number | null
  query: string
  scopeSummary: string
  projectScope: string | null
  onProjectSelect: (project: string) => void
  loading: boolean
  streamPhase: 'idle' | 'lexical' | 'reranked'
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

function buildProjectFacets(results: SearchResultItem[]): Array<{ slug: string; count: number }> {
  return buildCountFacets(results.map((result) => result.project_slug)).map(({ value, count }) => ({
    slug: value,
    count,
  }))
}

function buildSignalFacets(results: SearchResultItem[]): Array<{ value: string; count: number }> {
  return buildCountFacets(results.flatMap((result) => result.match_signals))
}

function buildTermFacets(results: SearchResultItem[]): Array<{ value: string; count: number }> {
  return buildCountFacets(results.flatMap((result) => result.matched_terms)).slice(0, 8)
}

function describePhase(
  loading: boolean,
  streamPhase: 'idle' | 'lexical' | 'reranked',
  semanticEnabled: boolean | null,
  rerankApplied: boolean | null,
): string | null {
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
  query,
  scopeSummary,
  projectScope,
  onProjectSelect,
  loading,
  streamPhase,
  semanticEnabled,
  rerankApplied,
}: SearchResultsProps) {
  const [signalFacet, setSignalFacet] = useState<string | null>(null)
  const [termFacet, setTermFacet] = useState<string | null>(null)

  useEffect(() => {
    setSignalFacet(null)
    setTermFacet(null)
  }, [query, projectScope])

  const projectFacets = buildProjectFacets(results)
  const signalFacets = buildSignalFacets(results)
  const termFacets = buildTermFacets(results)
  const phaseDescription = describePhase(loading, streamPhase, semanticEnabled, rerankApplied)

  const filteredResults = results.filter((result) => {
    if (signalFacet && !result.match_signals.includes(signalFacet)) {
      return false
    }
    if (termFacet && !result.matched_terms.includes(termFacet)) {
      return false
    }
    return true
  })

  if (results.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/40 px-6 py-10 text-center text-sm text-muted-foreground">
        No results found for "{query}" within {scopeSummary}.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border/70 bg-card/50 p-4">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <div className="text-sm font-medium text-foreground">
                {filteredResults.length} visible result{filteredResults.length === 1 ? '' : 's'} for "{query}"
                {filteredResults.length !== results.length ? ` (${results.length} total)` : ''}
              </div>
              <div className="text-sm text-muted-foreground">
                Searching {scopeSummary}
                {latencyMs != null ? ` in ${latencyMs}ms` : ''}
              </div>
            </div>
            {phaseDescription && (
              <div className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-xs text-muted-foreground">
                {phaseDescription}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-4">
            {!projectScope && projectFacets.length > 1 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Projects
                </span>
                {projectFacets.map((facet) => (
                  <Button
                    key={facet.slug}
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => onProjectSelect(facet.slug)}
                  >
                    {facet.slug} ({facet.count})
                  </Button>
                ))}
              </div>
            )}

            {signalFacets.length > 1 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Signals
                </span>
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
            )}

            {termFacets.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Exact Terms
                </span>
                {termFacets.map((facet) => (
                  <Button
                    key={facet.value}
                    type="button"
                    variant={termFacet === facet.value ? 'secondary' : 'outline'}
                    size="xs"
                    onClick={() => setTermFacet(termFacet === facet.value ? null : facet.value)}
                  >
                    {facet.value} ({facet.count})
                  </Button>
                ))}
              </div>
            )}

            {(projectScope || signalFacet || termFacet) && (
              <div className="flex flex-wrap items-center gap-2">
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
                  }}
                >
                  Clear facets
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {filteredResults.map((result) => (
        <Link
          key={result.chunk_id || `${result.project_slug}:${result.document_path}:${result.version_number}`}
          to="/projects/$slug/docs/$"
          params={{ slug: result.project_slug, _splat: result.document_path }}
          className="block"
        >
          <Card className="border border-border/80 transition-colors hover:bg-accent/40">
            <CardHeader>
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <CardTitle className="truncate">{result.document_title}</CardTitle>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {result.project_slug} / {result.document_path}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="outline">v{result.version_number}</Badge>
                  {(result.line_start > 0 || result.line_end > 0) && (
                    <Badge variant="outline">
                      lines {result.line_start}-{result.line_end}
                    </Badge>
                  )}
                  <span className="text-muted-foreground">{result.fused_score.toFixed(4)}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {result.match_signals.map((signal) => (
                  <Badge key={signal} variant="secondary" className="text-xs">
                    {signal}
                  </Badge>
                ))}
                {result.heading_path && (
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {result.heading_path}
                  </span>
                )}
              </div>

              <p className="text-sm leading-6 text-foreground/85">{result.snippet}</p>

              {result.matched_terms.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {result.matched_terms.map((term) => (
                    <Badge key={term} variant="secondary" className="text-xs">
                      {term}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}
