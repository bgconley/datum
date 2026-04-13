export type SearchVersionMode = 'current' | 'all' | 'as_of'
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
  limit: number
}

export interface SearchRouteState {
  query?: string
  project?: string
  mode?: SearchMode
  scope?: SearchVersionMode
  as_of?: string
  limit?: number
}

export const DEFAULT_SEARCH_DRAFT: SearchDraft = {
  query: '',
  project: '',
  mode: 'find_docs',
  versionMode: 'current',
  asOf: '',
  limit: 20,
}

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
      limit,
    }
  }

  return {
    query: search.query ?? '',
    project: search.project ?? '',
    mode,
    versionMode: scope === 'all' ? 'all' : 'current',
    asOf: '',
    limit,
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
  if (draft.limit !== DEFAULT_SEARCH_DRAFT.limit) {
    next.limit = draft.limit
  }

  return next
}
