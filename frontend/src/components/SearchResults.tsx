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
}

function buildProjectFacets(results: SearchResultItem[]): Array<{ slug: string; count: number }> {
  const counts = new Map<string, number>()
  for (const result of results) {
    counts.set(result.project_slug, (counts.get(result.project_slug) ?? 0) + 1)
  }

  return [...counts.entries()]
    .map(([slug, count]) => ({ slug, count }))
    .sort((left, right) => right.count - left.count || left.slug.localeCompare(right.slug))
}

export function SearchResults({
  results,
  latencyMs,
  query,
  scopeSummary,
  projectScope,
  onProjectSelect,
}: SearchResultsProps) {
  const projectFacets = buildProjectFacets(results)

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
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <div className="text-sm font-medium text-foreground">
              {results.length} result{results.length === 1 ? '' : 's'} for "{query}"
            </div>
            <div className="text-sm text-muted-foreground">
              Searching {scopeSummary}
              {latencyMs != null ? ` in ${latencyMs}ms` : ''}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!projectScope && projectFacets.length > 1 && (
              <>
                <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Project facets
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
              </>
            )}
            {projectScope && (
              <Button type="button" variant="outline" size="xs" onClick={() => onProjectSelect('')}>
                Clear project filter
              </Button>
            )}
          </div>
        </div>
      </div>

      {results.map((result) => (
        <a
          key={result.chunk_id || `${result.project_slug}:${result.document_path}:${result.version_number}`}
          href={`#/${result.project_slug}/${result.document_path}`}
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
        </a>
      ))}
    </div>
  )
}
