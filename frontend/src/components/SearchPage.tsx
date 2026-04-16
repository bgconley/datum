import { startTransition, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import {
  api,
  type AnswerModeResponse,
  type Project,
  type SavedSearchItem,
  type SearchEntityFacet,
  type SearchRequestParams,
  type SearchResultItem,
  type SearchStreamEvent,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { queryKeys } from '@/lib/query-keys'
import {
  DEFAULT_SEARCH_DRAFT,
  draftFromRouteSearch,
  draftsEqual,
  type SearchDraft,
  type SearchRouteState,
} from '@/lib/search-route'
import { useProjectsQuery } from '@/lib/workspace-query'
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
    mode: draft.mode,
    version_scope: draft.versionMode,
  }
  if (draft.mode === 'ask_question') {
    request.answer_mode = true
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

  if (draft.versionMode === 'snapshot') {
    const snapshot = draft.snapshot.trim()
    if (!snapshot) {
      return null
    }
    request.version_scope = `snapshot:${snapshot}`
  }

  if (draft.versionMode === 'branch') {
    const branch = draft.branch.trim()
    if (!branch) {
      return null
    }
    request.version_scope = `branch:${branch}`
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
        : draft.versionMode === 'snapshot'
          ? draft.snapshot.trim()
            ? `snapshot ${draft.snapshot.trim()}`
            : 'a named snapshot'
          : draft.versionMode === 'branch'
            ? draft.branch.trim()
              ? `branch ${draft.branch.trim()}`
              : 'a branch head'
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
  const [draft, setDraft] = useState<SearchDraft>(() => draftFromRouteSearch(routeSearch))
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [entityFacets, setEntityFacets] = useState<SearchEntityFacet[]>([])
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const [answer, setAnswer] = useState<AnswerModeResponse | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [searchOptionsOpen, setSearchOptionsOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [streamPhase, setStreamPhase] = useState<'idle' | 'lexical' | 'reranked' | 'answer_ready'>('idle')
  const [semanticEnabled, setSemanticEnabled] = useState<boolean | null>(null)
  const [rerankApplied, setRerankApplied] = useState<boolean | null>(null)
  const queryClient = useQueryClient()

  const projectsQuery = useProjectsQuery()
  const projects = projectsQuery.data ?? []
  const savedSearchesQuery = useQuery({
    queryKey: draft.project ? queryKeys.savedSearches(draft.project) : ['saved-searches', 'idle'],
    queryFn: () => api.savedSearches.list(draft.project!),
    enabled: Boolean(draft.project),
  })
  const savedSearches = savedSearchesQuery.data ?? []
  const lastExecutedRouteKeyRef = useRef('')
  const routeDraft = useMemo(
    () => draftFromRouteSearch(routeSearch),
    [
      routeSearch.as_of,
      routeSearch.limit,
      routeSearch.mode,
      routeSearch.project,
      routeSearch.query,
      routeSearch.branch,
      routeSearch.scope,
      routeSearch.snapshot,
    ],
  )
  const routeDraftKey = useMemo(() => JSON.stringify(routeDraft), [routeDraft])

  const executeSearch = useEffectEvent(async (nextDraft: SearchDraft) => {
    const request = buildSearchRequest(nextDraft)
    if (!request) {
      startTransition(() => {
        setQuery(nextDraft.query.trim())
        setResults([])
        setEntityFacets([])
        setLatencyMs(null)
        setAnswer(null)
        setSearched(Boolean(nextDraft.query.trim()))
        setStreamPhase('idle')
        setSemanticEnabled(null)
        setRerankApplied(null)
        setError(
          nextDraft.versionMode === 'as_of'
            ? 'Choose a valid as-of timestamp before searching.'
            : nextDraft.versionMode === 'snapshot'
              ? 'Choose a snapshot name before searching.'
              : nextDraft.versionMode === 'branch'
                ? 'Choose a branch name before searching.'
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
    setEntityFacets([])
    setAnswer(null)

    try {
      await api.searchStream(request, async (event: SearchStreamEvent) => {
        if (event.event === 'error') {
          throw new Error(event.message || 'Search stream failed')
        }

        startTransition(() => {
          setResults(event.results)
          setEntityFacets(event.entity_facets)
          setLatencyMs(event.latency_ms)
          setQuery(event.query)
          setStreamPhase(event.phase ?? 'reranked')
          setSemanticEnabled(event.semantic_enabled)
          setRerankApplied(event.rerank_applied)
          setAnswer(event.answer ?? null)
        })
      })
    } catch (err) {
      try {
        const response = await api.search(request)
        startTransition(() => {
          setResults(response.results)
          setEntityFacets(response.entity_facets)
          setLatencyMs(response.latency_ms)
          setQuery(response.query)
          setStreamPhase(response.answer ? 'answer_ready' : 'reranked')
          setSemanticEnabled(null)
          setRerankApplied(false)
          setAnswer(response.answer ?? null)
        })
      } catch (fallbackErr) {
        const message = fallbackErr instanceof Error
          ? fallbackErr.message
          : err instanceof Error
            ? err.message
            : 'Search failed'
        startTransition(() => {
          setResults([])
          setEntityFacets([])
          setLatencyMs(null)
          setAnswer(null)
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
    setDraft((current) => (draftsEqual(current, routeDraft) ? current : routeDraft))

    if (routeDraft.query.trim()) {
      if (lastExecutedRouteKeyRef.current !== routeDraftKey) {
        lastExecutedRouteKeyRef.current = routeDraftKey
        void executeSearch(routeDraft)
      }
      return
    }

    lastExecutedRouteKeyRef.current = ''
    startTransition(() => {
      setQuery('')
      setResults([])
      setEntityFacets([])
      setLatencyMs(null)
      setAnswer(null)
      setSearched(false)
      setStreamPhase('idle')
      setSemanticEnabled(null)
      setRerankApplied(null)
      setError(null)
    })
  }, [executeSearch, routeDraft, routeDraftKey])

  useEffect(() => {
    if (!searched) {
      setSearchOptionsOpen(false)
    }
  }, [searched])

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
        setEntityFacets([])
        setLatencyMs(null)
        setAnswer(null)
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

  const handleSaveSearch = async () => {
    if (!draft.project) {
      setError('Choose a project before saving a search.')
      return
    }
    const request = buildSearchRequest(draft)
    if (!request) {
      setError('Enter a valid query before saving.')
      return
    }

    const name = window.prompt('Saved search name')
    if (!name) {
      return
    }

    await api.savedSearches.create(draft.project, {
      name,
      query_text: request.query,
      filters: {
        mode: draft.mode,
        version_scope: request.version_scope ?? 'current',
        limit: request.limit ?? 20,
      },
    })
    await queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches(draft.project) })
  }

  const handleLoadSavedSearch = (savedSearch: SavedSearchItem) => {
    const filters = savedSearch.filters ?? {}
    const versionScope =
      typeof filters.version_scope === 'string' ? filters.version_scope : 'current'
    const snapshot = versionScope.startsWith('snapshot:') ? versionScope.slice(9) : ''
    const branch = versionScope.startsWith('branch:') ? versionScope.slice(7) : ''
    const nextDraft: SearchDraft = {
      ...draft,
      query: savedSearch.query_text,
      project: draft.project,
      mode:
        savedSearch.filters && typeof savedSearch.filters.mode === 'string'
          ? (savedSearch.filters.mode as SearchDraft['mode'])
          : draft.mode,
      limit: typeof filters.limit === 'number' ? filters.limit : draft.limit,
      versionMode:
        versionScope === 'all'
          ? 'all'
          : versionScope.startsWith('as_of:')
            ? 'as_of'
            : versionScope.startsWith('snapshot:')
              ? 'snapshot'
              : versionScope.startsWith('branch:')
                ? 'branch'
            : 'current',
      asOf: versionScope.startsWith('as_of:') ? versionScope.slice(6) : '',
      snapshot,
      branch,
    }
    setDraft(nextDraft)
    navigateToSearch(nextDraft)
  }

  const handleDeleteSavedSearch = async (savedSearch: SavedSearchItem) => {
    if (!draft.project) {
      return
    }
    await api.savedSearches.delete(draft.project, savedSearch.id)
    await queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches(draft.project) })
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

  const handleDraftChange = (nextDraft: SearchDraft) => {
    let adjustedDraft = nextDraft
    if (nextDraft.mode === 'search_history' && nextDraft.versionMode === 'current') {
      adjustedDraft = { ...nextDraft, versionMode: 'all' }
    }
    if (nextDraft.mode === 'compare_over_time' && nextDraft.versionMode === 'current') {
      adjustedDraft = { ...nextDraft, versionMode: 'as_of' }
    }
    if (adjustedDraft.mode === 'find_docs' && adjustedDraft.versionMode === 'as_of' && !adjustedDraft.asOf) {
      adjustedDraft = { ...adjustedDraft, versionMode: 'current' }
    }
    if (adjustedDraft.versionMode !== 'as_of') {
      adjustedDraft = { ...adjustedDraft, asOf: '' }
    }
    if (adjustedDraft.versionMode !== 'snapshot') {
      adjustedDraft = { ...adjustedDraft, snapshot: '' }
    }
    if (adjustedDraft.versionMode !== 'branch') {
      adjustedDraft = { ...adjustedDraft, branch: '' }
    }
    setDraft(adjustedDraft)
  }

  const scopeSummary = describeScope(draft, projects)

  const compactSearch = searched
  const hasResults = searched && !error

  return (
    <div className={compactSearch ? 'flex flex-col gap-[14px] px-[24px] py-[20px]' : 'mx-auto flex max-w-5xl flex-col gap-6 p-8'}>
      {!searched && (
        <div className="rounded border border-border bg-white p-8 shadow-sm">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Search workspace
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">Search</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
            Streaming retrieval across indexed documents: lexical hits land first, then exact-term
            and semantic signals are fused and reranked. Search state lives in the routed URL so
            scoped queries remain durable and shareable.
          </p>
        </div>
      )}

      <SearchBar
        value={draft}
        projects={projects}
        loading={loading}
        compact={compactSearch}
        hideQuery={compactSearch}
        showAdvanced={searchOptionsOpen}
        onChange={handleDraftChange}
        onSearch={handleSearch}
        onReset={handleReset}
        onToggleAdvanced={() => setSearchOptionsOpen((current) => !current)}
      />

      {compactSearch && searchOptionsOpen && draft.project && (
        <div className="flex items-center justify-end gap-2">
          <Button size="sm" variant="outline" onClick={() => void handleSaveSearch()}>
            Save current search
          </Button>
        </div>
      )}

      {!searched && draft.project && (
        <div className="rounded border border-border bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Saved searches
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Persist project-scoped search presets with query text and retrieval scope.
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={() => void handleSaveSearch()}>
              Save current search
            </Button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {savedSearches.length === 0 ? (
              <div className="text-sm text-muted-foreground">No saved searches yet.</div>
            ) : (
              savedSearches.map((savedSearch) => (
                <div
                  key={savedSearch.id}
                  className="flex items-center gap-2 rounded border border-border bg-background px-3 py-2 text-sm"
                >
                  <button
                    type="button"
                    className="truncate text-left hover:text-foreground"
                    onClick={() => handleLoadSavedSearch(savedSearch)}
                  >
                    {savedSearch.name}
                  </button>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => void handleDeleteSavedSearch(savedSearch)}
                  >
                    Delete
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {!searched && (
        <div className="rounded border border-dashed border-border bg-white px-6 py-10 text-sm text-muted-foreground">
          Press <kbd className="rounded border px-1 py-0.5 text-xs">/</kbd> anywhere in the app
          to jump here, then search by heading text, exact identifiers, env vars like
          <span className="mx-1 font-mono text-foreground">DATABASE_URL</span>, or routes like
          <span className="mx-1 font-mono text-foreground">GET /api/v1/health</span>.
        </div>
      )}

      {error && (
        <div className="rounded border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {searched && !error && (
        <SearchResults
          results={results}
          latencyMs={latencyMs}
          answer={answer}
          query={query}
          scopeSummary={scopeSummary}
          projectScope={draft.project || null}
          searchMode={draft.mode}
          onProjectSelect={handleProjectFacet}
          entityFacets={entityFacets}
          loading={loading}
          streamPhase={streamPhase}
          semanticEnabled={semanticEnabled}
          rerankApplied={rerankApplied}
        />
      )}
    </div>
  )
}
