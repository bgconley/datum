export type SearchVersionMode = 'current' | 'all' | 'as_of' | 'snapshot' | 'branch'
export type SearchMode =
  | 'find_docs'
  | 'ask_question'
  | 'find_decisions'
  | 'search_history'
  | 'compare_over_time'

export interface SearchDraft {
  query: string
  project: string
  mode: SearchMode
  versionMode: SearchVersionMode
  asOf: string
  snapshot: string
  branch: string
  limit: number
}

export interface SearchRouteState {
  query?: string
  project?: string
  mode?: SearchMode
  scope?: SearchVersionMode
  as_of?: string
  snapshot?: string
  branch?: string
  limit?: number
}

export const DEFAULT_SEARCH_DRAFT: SearchDraft = {
  query: '',
  project: '',
  mode: 'find_docs',
  versionMode: 'current',
  asOf: '',
  snapshot: '',
  branch: '',
  limit: 20,
}

export function createSearchDraftForLaunch(project?: string | null): SearchDraft {
  return {
    ...DEFAULT_SEARCH_DRAFT,
    project: project ?? '',
  }
}

const VALID_SEARCH_MODES = new Set<SearchMode>([
  'find_docs',
  'ask_question',
  'find_decisions',
  'search_history',
  'compare_over_time',
])

const VALID_SEARCH_SCOPES = new Set<SearchVersionMode>([
  'current',
  'all',
  'as_of',
  'snapshot',
  'branch',
])

export function toDatetimeLocalValue(value: string): string {
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

export function draftsEqual(left: SearchDraft, right: SearchDraft): boolean {
  return (
    left.query === right.query &&
    left.project === right.project &&
    left.mode === right.mode &&
    left.versionMode === right.versionMode &&
    left.asOf === right.asOf &&
    left.snapshot === right.snapshot &&
    left.branch === right.branch &&
    left.limit === right.limit
  )
}

export function draftFromRouteSearch(search: SearchRouteState): SearchDraft {
  const scope = search.scope ?? 'current'
  const mode = search.mode ?? DEFAULT_SEARCH_DRAFT.mode
  const parsedLimit = Number(search.limit ?? DEFAULT_SEARCH_DRAFT.limit)
  const limit = Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : DEFAULT_SEARCH_DRAFT.limit

  if (scope === 'as_of') {
    return {
      query: search.query ?? '',
      project: search.project ?? '',
      mode,
      versionMode: 'as_of',
      asOf: search.as_of ? toDatetimeLocalValue(search.as_of) : '',
      snapshot: '',
      branch: '',
      limit,
    }
  }

  if (scope === 'snapshot') {
    return {
      query: search.query ?? '',
      project: search.project ?? '',
      mode,
      versionMode: 'snapshot',
      asOf: '',
      snapshot: search.snapshot ?? '',
      branch: '',
      limit,
    }
  }

  if (scope === 'branch') {
    return {
      query: search.query ?? '',
      project: search.project ?? '',
      mode,
      versionMode: 'branch',
      asOf: '',
      snapshot: '',
      branch: search.branch ?? '',
      limit,
    }
  }

  return {
    query: search.query ?? '',
    project: search.project ?? '',
    mode,
    versionMode: scope === 'all' ? 'all' : 'current',
    asOf: '',
    snapshot: '',
    branch: '',
    limit,
  }
}

export function parseSearchRouteState(searchStr: string): SearchRouteState {
  const params = new URLSearchParams(searchStr.startsWith('?') ? searchStr.slice(1) : searchStr)
  const mode = params.get('mode')
  const scope = params.get('scope')
  const limitValue = params.get('limit')
  const parsedLimit = limitValue ? Number(limitValue) : undefined

  return {
    query: params.get('query') ?? undefined,
    project: params.get('project') ?? undefined,
    mode: mode && VALID_SEARCH_MODES.has(mode as SearchMode) ? (mode as SearchMode) : undefined,
    scope:
      scope && VALID_SEARCH_SCOPES.has(scope as SearchVersionMode)
        ? (scope as SearchVersionMode)
        : undefined,
    as_of: params.get('as_of') ?? undefined,
    snapshot: params.get('snapshot') ?? undefined,
    branch: params.get('branch') ?? undefined,
    limit:
      parsedLimit != null && Number.isFinite(parsedLimit) && parsedLimit > 0
        ? parsedLimit
        : undefined,
  }
}

export function routeSearchFromDraft(draft: SearchDraft): SearchRouteState {
  const query = draft.query.trim()
  const next: SearchRouteState = {}

  if (query) {
    next.query = query
  }
  if (draft.project) {
    next.project = draft.project
  }
  if (draft.mode !== DEFAULT_SEARCH_DRAFT.mode) {
    next.mode = draft.mode
  }
  if (draft.versionMode !== DEFAULT_SEARCH_DRAFT.versionMode) {
    next.scope = draft.versionMode
  }
  if (draft.versionMode === 'as_of' && draft.asOf) {
    const asOfDate = new Date(draft.asOf)
    if (!Number.isNaN(asOfDate.getTime())) {
      next.as_of = asOfDate.toISOString()
    }
  }
  if (draft.versionMode === 'snapshot' && draft.snapshot.trim()) {
    next.snapshot = draft.snapshot.trim()
  }
  if (draft.versionMode === 'branch' && draft.branch.trim()) {
    next.branch = draft.branch.trim()
  }
  if (draft.limit !== DEFAULT_SEARCH_DRAFT.limit) {
    next.limit = draft.limit
  }

  return next
}

export function createSearchRouteStateForLaunch(project?: string | null): SearchRouteState {
  return routeSearchFromDraft(createSearchDraftForLaunch(project))
}

export function replaceSearchRouteProject(
  search: SearchRouteState | undefined,
  project: string,
): SearchRouteState {
  if (!search) {
    return { project }
  }

  if (!search.project) {
    return { ...search }
  }

  return {
    ...search,
    project,
  }
}
