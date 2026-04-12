import { startTransition, useEffect, useEffectEvent, useState } from 'react'

import { SearchBar, type SearchDraft } from './SearchBar'
import { SearchResults } from './SearchResults'
import {
  api,
  type Project,
  type SearchRequestParams,
  type SearchResultItem,
  type SearchStreamEvent,
} from '@/lib/api'

const DEFAULT_SEARCH_DRAFT: SearchDraft = {
  query: '',
  project: '',
  versionMode: 'current',
  asOf: '',
  limit: 20,
}

function toDatetimeLocalValue(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const pad = (part: number) => String(part).padStart(2, '0')
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join('-') + `T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function draftsEqual(left: SearchDraft, right: SearchDraft): boolean {
  return (
    left.query === right.query &&
    left.project === right.project &&
    left.versionMode === right.versionMode &&
    left.asOf === right.asOf &&
    left.limit === right.limit
  )
}

function parseDraftFromRoute(route: string): SearchDraft {
  const [routeName, search = ''] = route.split('?', 2)
  if (routeName !== 'search' || !search) {
    return DEFAULT_SEARCH_DRAFT
  }

  const params = new URLSearchParams(search)
  const scope = params.get('scope') ?? 'current'
  const legacyVersionScope = params.get('version_scope')
  const effectiveScope = legacyVersionScope ?? scope
  const parsedLimit = Number(params.get('limit') ?? DEFAULT_SEARCH_DRAFT.limit)
  const limit = Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : DEFAULT_SEARCH_DRAFT.limit

  if (effectiveScope.startsWith('as_of:')) {
    return {
      query: params.get('query') ?? '',
      project: params.get('project') ?? '',
      versionMode: 'as_of',
      asOf: toDatetimeLocalValue(effectiveScope.slice(6)),
      limit,
    }
  }

  return {
    query: params.get('query') ?? '',
    project: params.get('project') ?? '',
    versionMode:
      effectiveScope === 'all' || effectiveScope === 'as_of' ? effectiveScope : 'current',
    asOf: params.get('as_of') ?? '',
    limit,
  }
}

function buildSearchHash(draft: SearchDraft): string {
  const params = new URLSearchParams()
  const query = draft.query.trim()
  if (query) {
    params.set('query', query)
  }
  if (draft.project) {
    params.set('project', draft.project)
  }
  if (draft.versionMode !== DEFAULT_SEARCH_DRAFT.versionMode) {
    params.set('scope', draft.versionMode)
  }
  if (draft.versionMode === 'as_of' && draft.asOf) {
    params.set('as_of', draft.asOf)
  }
  if (draft.limit !== DEFAULT_SEARCH_DRAFT.limit) {
    params.set('limit', String(draft.limit))
  }

  const queryString = params.toString()
  return queryString ? `#/search?${queryString}` : '#/search'
}

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
  route: string
}

export function SearchPage({ route }: SearchPageProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [draft, setDraft] = useState<SearchDraft>(() => parseDraftFromRoute(route))
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [streamPhase, setStreamPhase] = useState<'idle' | 'lexical' | 'hybrid'>('idle')
  const [semanticEnabled, setSemanticEnabled] = useState<boolean | null>(null)

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
        setError(
          nextDraft.versionMode === 'as_of'
            ? 'Choose a valid as-of timestamp before searching.'
            : null
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

    try {
      await api.searchStream(request, async (event: SearchStreamEvent) => {
        if (event.event === 'error') {
          throw new Error(event.message || 'Search stream failed')
        }

        startTransition(() => {
          setResults(event.results)
          setLatencyMs(event.latency_ms)
          setQuery(event.query)
          setStreamPhase(event.phase ?? 'hybrid')
          setSemanticEnabled(event.semantic_enabled)
        })
      })
    } catch (err) {
      try {
        const response = await api.search(request)
        startTransition(() => {
          setResults(response.results)
          setLatencyMs(response.latency_ms)
          setQuery(response.query)
          setStreamPhase('hybrid')
          setSemanticEnabled(null)
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
          setError(message)
        })
      }
    } finally {
      setLoading(false)
    }
  })

  useEffect(() => {
    const nextDraft = parseDraftFromRoute(route)
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
      setError(null)
    })
  }, [route, executeSearch])

  const handleSearch = async () => {
    const nextHash = buildSearchHash(draft)
    if (window.location.hash === nextHash) {
      await executeSearch(draft)
      return
    }
    window.location.hash = nextHash
  }

  const handleReset = () => {
    setDraft(DEFAULT_SEARCH_DRAFT)
    if (window.location.hash === '#/search') {
      startTransition(() => {
        setQuery('')
        setResults([])
        setLatencyMs(null)
        setSearched(false)
        setStreamPhase('idle')
        setSemanticEnabled(null)
        setError(null)
      })
      return
    }
    window.location.hash = '#/search'
  }

  const handleProjectFacet = (project: string) => {
    const nextDraft = { ...draft, project }
    setDraft(nextDraft)
    const nextHash = buildSearchHash(nextDraft)
    if (window.location.hash === nextHash) {
      void executeSearch(nextDraft)
      return
    }
    window.location.hash = nextHash
  }

  const scopeSummary = describeScope(draft, projects)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <div>
        <div className="text-sm uppercase tracking-[0.24em] text-muted-foreground">Phase 2</div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Search</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          Hybrid retrieval across indexed documents using lexical search, technical-term matches,
          and semantic vectors when the embedding service is available. Search state is kept in the
          URL so scoped queries are durable and shareable.
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
        />
      )}
    </div>
  )
}
