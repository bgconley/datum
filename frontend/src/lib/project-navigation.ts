import type { SearchRouteState } from '@/lib/search-route'
import { parseSearchRouteState } from '@/lib/search-route'
import { resolveSelectedProject } from '@/lib/route-project'
import type {
  ProjectVisitSection,
  ProjectVisitSnapshot,
} from '@/lib/project-preferences'
import { recordProjectVisit } from '@/lib/project-preferences'

interface DocumentRouteSearchState {
  sourceQuery?: string
  sourceQueryLabel?: string
  sourceSnippet?: string
  sourceHeading?: string
  sourceSignals?: string
  sourceVersion?: number
  sourceStart?: number
  sourceEnd?: number
  sourceChunkId?: string
}

type ProjectNavigateTarget =
  | { to: '/projects/$slug'; params: { slug: string } }
  | { to: '/projects/$slug/inbox'; params: { slug: string } }
  | { to: '/projects/$slug/sessions'; params: { slug: string } }
  | { to: '/projects/$slug/docs/$'; params: { slug: string; _splat: string }; search?: DocumentRouteSearchState }
  | { to: '/search'; search?: SearchRouteState }

export interface ParsedProjectLocation {
  slug: string | null
  section: ProjectVisitSection
  pathname: string
  searchStr: string
  docPath?: string
  searchState?: SearchRouteState
  documentSearch?: DocumentRouteSearchState
}

function parseDocumentRouteSearch(searchStr: string): DocumentRouteSearchState {
  const params = new URLSearchParams(searchStr.startsWith('?') ? searchStr.slice(1) : searchStr)
  const getNumber = (key: string) => {
    const value = params.get(key)
    if (value == null) {
      return undefined
    }
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }

  return {
    sourceQuery: params.get('sourceQuery') ?? undefined,
    sourceQueryLabel: params.get('sourceQueryLabel') ?? undefined,
    sourceSnippet: params.get('sourceSnippet') ?? undefined,
    sourceHeading: params.get('sourceHeading') ?? undefined,
    sourceSignals: params.get('sourceSignals') ?? undefined,
    sourceVersion: getNumber('sourceVersion'),
    sourceStart: getNumber('sourceStart'),
    sourceEnd: getNumber('sourceEnd'),
    sourceChunkId: params.get('sourceChunkId') ?? undefined,
  }
}

function stripProjectPrefix(pathname: string, slug: string) {
  return pathname.slice(`/projects/${slug}`.length)
}

export function parseProjectLocation(pathname: string, searchStr: string): ParsedProjectLocation {
  const slug = resolveSelectedProject(pathname, searchStr)

  if (pathname === '/search') {
    return {
      slug,
      section: slug ? 'search' : 'unknown',
      pathname,
      searchStr,
      searchState: parseSearchRouteState(searchStr),
    }
  }

  if (!slug || !pathname.startsWith(`/projects/${slug}`)) {
    return {
      slug: null,
      section: 'unknown',
      pathname,
      searchStr,
    }
  }

  const remainder = stripProjectPrefix(pathname, slug)

  if (remainder === '' || remainder === '/') {
    return { slug, section: 'dashboard', pathname, searchStr }
  }

  if (remainder === '/inbox' || remainder === '/review') {
    return { slug, section: 'inbox', pathname, searchStr }
  }

  if (remainder === '/sessions') {
    return { slug, section: 'sessions', pathname, searchStr }
  }

  if (remainder.startsWith('/docs/')) {
    return {
      slug,
      section: 'document',
      pathname,
      searchStr,
      docPath: decodeURIComponent(remainder.slice('/docs/'.length)),
      documentSearch: parseDocumentRouteSearch(searchStr),
    }
  }

  return { slug, section: 'unknown', pathname, searchStr }
}

export function createProjectVisitSnapshot(pathname: string, searchStr: string): ProjectVisitSnapshot | null {
  const parsed = parseProjectLocation(pathname, searchStr)
  if (!parsed.slug) {
    return null
  }

  return {
    slug: parsed.slug,
    pathname: parsed.pathname,
    searchStr: parsed.searchStr,
    section: parsed.section,
    visitedAt: new Date().toISOString(),
  }
}

export function recordProjectLocation(pathname: string, searchStr: string) {
  const snapshot = createProjectVisitSnapshot(pathname, searchStr)
  if (!snapshot) {
    return
  }

  recordProjectVisit(snapshot)
}

export function describeProjectVisit(snapshot: ProjectVisitSnapshot) {
  switch (snapshot.section) {
    case 'dashboard':
      return 'Resume on dashboard'
    case 'inbox':
      return 'Resume in inbox'
    case 'sessions':
      return 'Resume in sessions'
    case 'search':
      return 'Resume search in same scope'
    case 'document':
      return 'Resume in last document'
    default:
      return 'Resume project'
  }
}

export function buildResumeTarget(snapshot: ProjectVisitSnapshot): ProjectNavigateTarget {
  const parsed = parseProjectLocation(snapshot.pathname, snapshot.searchStr)
  if (!parsed.slug) {
    return {
      to: '/projects/$slug',
      params: { slug: snapshot.slug },
    }
  }

  switch (parsed.section) {
    case 'dashboard':
      return { to: '/projects/$slug', params: { slug: parsed.slug } }
    case 'inbox':
      return { to: '/projects/$slug/inbox', params: { slug: parsed.slug } }
    case 'sessions':
      return { to: '/projects/$slug/sessions', params: { slug: parsed.slug } }
    case 'search':
      return { to: '/search', search: parsed.searchState }
    case 'document':
      return {
        to: '/projects/$slug/docs/$',
        params: {
          slug: parsed.slug,
          _splat: parsed.docPath ?? '',
        },
        search: parsed.documentSearch,
      }
    default:
      return { to: '/projects/$slug', params: { slug: snapshot.slug } }
  }
}

export function buildProjectSwitchTarget(
  pathname: string,
  searchStr: string,
  destinationSlug: string,
): ProjectNavigateTarget {
  const parsed = parseProjectLocation(pathname, searchStr)

  switch (parsed.section) {
    case 'dashboard':
      return { to: '/projects/$slug', params: { slug: destinationSlug } }
    case 'inbox':
      return { to: '/projects/$slug/inbox', params: { slug: destinationSlug } }
    case 'sessions':
      return { to: '/projects/$slug/sessions', params: { slug: destinationSlug } }
    case 'search':
      return {
        to: '/search',
        search: {
          ...(parsed.searchState ?? {}),
          project: destinationSlug,
        },
      }
    case 'document':
    case 'unknown':
    default:
      return { to: '/projects/$slug', params: { slug: destinationSlug } }
  }
}

export function navigateToProjectTarget(
  navigate: (options: any) => unknown,
  target: ProjectNavigateTarget,
) {
  if (target.to === '/search') {
    navigate({
      to: '/search',
      search: target.search,
    })
    return
  }

  if (target.to === '/projects/$slug/docs/$') {
    navigate({
      to: '/projects/$slug/docs/$',
      params: target.params,
      search: target.search,
    })
    return
  }

  navigate({
    to: target.to,
    params: target.params,
  })
}
