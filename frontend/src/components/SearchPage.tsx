import { startTransition, useEffect, useEffectEvent, useState } from 'react'

import {
  api,
  type Project,
  type SearchRequestParams,
  type SearchResultItem,
  type SearchStreamEvent,
} from '@/lib/api'
import {
  DEFAULT_SEARCH_DRAFT,
  draftFromRouteSearch,
  draftsEqual,
  type SearchDraft,
  type SearchRouteState,
} from '@/lib/search-route'
import { SearchBar } from './SearchBar'
import { SearchResults } from './SearchResults'

function buildSearchRequest(draft: SearchDraft): SearchRequestParams | null {
  const query = draft.query.trim()
  if (!query) {
    return null
  }

  const request: SearchRequestParams = {
    query,
    limit: draft.limit,
    version_scope: draft.versionMode,
  }
  if (draft.project) {
    request.project = draft.project
  }

  if (draft.versionMode === 'as_of') {
    if (!draft.asOf) {
      return null
    }

    const asOfDate = new Date(draft.asOf)
    if (Number.isNaN(asOfDate.getTime())) {
      return null
    }
    request.version_scope = `as_of:${asOfDate.toISOString()}`
  }

  return request
}

function describeScope(draft: SearchDraft, projects: Project[]): string {
  const scopeLabel =
    draft.versionMode === 'all'
      ? 'all versions'
      : draft.versionMode === 'as_of'
        ? draft.asOf
          ? `versions current at ${new Date(draft.asOf).toLocaleString()}`
          : 'versions at a selected timestamp'
        : 'current versions'

  if (!draft.project) {
    return scopeLabel
  }

  const projectName = projects.find((project) => project.slug === draft.project)?.name ?? draft.project
  return `${scopeLabel} in ${projectName}`
}

interface SearchPageProps {
  routeSearch: SearchRouteState
  navigateToSearch: (draft: SearchDraft) => void
}

export function SearchPage({ routeSearch, navigateToSearch }: SearchPageProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [draft, setDraft] = useState<SearchDraft>(() => draftFromRouteSearch(routeSearch))
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [streamPhase, setStreamPhase] = useState<'idle' | 'lexical' | 'reranked'>('idle')
  const [semanticEnabled, setSemanticEnabled] = useState<boolean | null>(null)
  const [rerankApplied, setRerankApplied] = useState<boolean | null>(null)

  useEffect(() => {
    api.projects.list().then(setProjects).catch((err) => {
      console.error(err)
    })
  }, [])

  const executeSearch = useEffectEvent(async (nextDraft: SearchDraft) => {
    const request = buildSearchRequest(nextDraft)
    if (!request) {
      startTransition(() => {
        setQuery(nextDraft.query.trim())
        setResults([])
        setLatencyMs(null)
        setSearched(Boolean(nextDraft.query.trim()))
        setStreamPhase('idle')
        setSemanticEnabled(null)
        setRerankApplied(null)
        setError(
          nextDraft.versionMode === 'as_of'
            ? 'Choose a valid as-of timestamp before searching.'
            : null,
        )
      })
      return
    }

    setLoading(true)
    setSearched(true)
    setError(null)
    setQuery(request.query)
    setStreamPhase('idle')
    setSemanticEnabled(null)
    setRerankApplied(null)

    try {
      await api.searchStream(request, async (event: SearchStreamEvent) => {
        if (event.event === 'error') {
          throw new Error(event.message || 'Search stream failed')
        }

        startTransition(() => {
          setResults(event.results)
          setLatencyMs(event.latency_ms)
          setQuery(event.query)
          setStreamPhase(event.phase ?? 'reranked')
          setSemanticEnabled(event.semantic_enabled)
          setRerankApplied(event.rerank_applied)
        })
      })
    } catch (err) {
      try {
        const response = await api.search(request)
        startTransition(() => {
          setResults(response.results)
          setLatencyMs(response.latency_ms)
          setQuery(response.query)
          setStreamPhase('reranked')
          setSemanticEnabled(null)
          setRerankApplied(false)
        })
      } catch (fallbackErr) {
        const message = fallbackErr instanceof Error
          ? fallbackErr.message
          : err instanceof Error
            ? err.message
            : 'Search failed'
        startTransition(() => {
          setResults([])
          setLatencyMs(null)
          setStreamPhase('idle')
          setSemanticEnabled(null)
          setRerankApplied(null)
          setError(message)
        })
      }
    } finally {
      setLoading(false)
    }
  })

  useEffect(() => {
    const nextDraft = draftFromRouteSearch(routeSearch)
    setDraft((current) => (draftsEqual(current, nextDraft) ? current : nextDraft))

    if (nextDraft.query.trim()) {
      void executeSearch(nextDraft)
      return
    }

    startTransition(() => {
      setQuery('')
      setResults([])
      setLatencyMs(null)
      setSearched(false)
      setStreamPhase('idle')
      setSemanticEnabled(null)
      setRerankApplied(null)
      setError(null)
    })
  }, [executeSearch, routeSearch])

  const handleSearch = async () => {
    const currentDraft = draftFromRouteSearch(routeSearch)
    if (draftsEqual(currentDraft, draft)) {
      await executeSearch(draft)
      return
    }
    navigateToSearch(draft)
  }

  const handleReset = () => {
    setDraft(DEFAULT_SEARCH_DRAFT)
    const currentDraft = draftFromRouteSearch(routeSearch)
    if (draftsEqual(currentDraft, DEFAULT_SEARCH_DRAFT)) {
      startTransition(() => {
        setQuery('')
        setResults([])
        setLatencyMs(null)
        setSearched(false)
        setStreamPhase('idle')
        setSemanticEnabled(null)
        setRerankApplied(null)
        setError(null)
      })
      return
    }
    navigateToSearch(DEFAULT_SEARCH_DRAFT)
  }

  const handleProjectFacet = (project: string) => {
    const nextDraft = { ...draft, project }
    setDraft(nextDraft)
    const currentDraft = draftFromRouteSearch(routeSearch)
    if (draftsEqual(currentDraft, nextDraft)) {
      void executeSearch(nextDraft)
      return
    }
    navigateToSearch(nextDraft)
  }

  const scopeSummary = describeScope(draft, projects)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Search workspace
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Search</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
          Streaming retrieval across indexed documents: lexical hits land first, then exact-term
          and semantic signals are fused and reranked. Search state lives in the routed URL so
          scoped queries remain durable and shareable.
        </p>
      </div>

      <SearchBar
        value={draft}
        projects={projects}
        loading={loading}
        onChange={setDraft}
        onSearch={handleSearch}
        onReset={handleReset}
      />

      {!searched && (
        <div className="rounded-xl border border-dashed border-border bg-card/40 px-6 py-10 text-sm text-muted-foreground">
          Press <kbd className="rounded border px-1 py-0.5 text-xs">/</kbd> anywhere in the app
          to jump here, then search by heading text, exact identifiers, env vars like
          <span className="mx-1 font-mono text-foreground">DATABASE_URL</span>, or routes like
          <span className="mx-1 font-mono text-foreground">GET /api/v1/health</span>.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {searched && !error && (
        <SearchResults
          results={results}
          latencyMs={latencyMs}
          query={query}
          scopeSummary={scopeSummary}
          projectScope={draft.project || null}
          onProjectSelect={handleProjectFacet}
          loading={loading}
          streamPhase={streamPhase}
          semanticEnabled={semanticEnabled}
          rerankApplied={rerankApplied}
        />
      )}
    </div>
  )
}
