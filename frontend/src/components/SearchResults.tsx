import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SearchResultItem } from '@/lib/api'

interface SearchResultsProps {
  results: SearchResultItem[]
  latencyMs?: number | null
  query: string
}

export function SearchResults({ results, latencyMs, query }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/40 px-6 py-10 text-center text-sm text-muted-foreground">
        No results found for "{query}".
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="text-sm text-muted-foreground">
        {results.length} result{results.length === 1 ? '' : 's'}
        {latencyMs != null ? ` in ${latencyMs}ms` : ''}
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
                  <span className="text-muted-foreground">{result.fused_score.toFixed(4)}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {result.heading_path && (
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {result.heading_path}
                </div>
              )}
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
