import { useState } from 'react'

import { SearchBar } from './SearchBar'
import { SearchResults } from './SearchResults'
import { api, type SearchResultItem } from '@/lib/api'

export function SearchPage() {
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (nextQuery: string) => {
    setQuery(nextQuery)
    setLoading(true)
    setSearched(true)
    setError(null)

    try {
      const response = await api.search(nextQuery)
      setResults(response.results)
      setLatencyMs(response.latency_ms)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Search failed'
      setResults([])
      setLatencyMs(null)
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <div>
        <div className="text-sm uppercase tracking-[0.24em] text-muted-foreground">Phase 2</div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Search</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Hybrid retrieval across indexed documents using lexical search, technical-term matches,
          and semantic vectors when the embedding service is available.
        </p>
      </div>

      <SearchBar onSearch={handleSearch} loading={loading} />

      {!searched && (
        <div className="rounded-xl border border-dashed border-border bg-card/40 px-6 py-10 text-sm text-muted-foreground">
          Press <kbd className="rounded border px-1 py-0.5 text-xs">/</kbd> anywhere in the app
          to jump here, then search by heading text, exact identifiers, or known routes like
          <span className="mx-1 font-mono text-foreground">/api/v1/health</span>.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {searched && !error && (
        <SearchResults results={results} latencyMs={latencyMs} query={query} />
      )}
    </div>
  )
}
