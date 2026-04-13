import { QueryClient } from '@tanstack/react-query'
import { Suspense, lazy } from 'react'
import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useNavigate,
} from '@tanstack/react-router'

import { CommandPalette } from '@/components/CommandPalette'
import { Layout } from '@/components/Layout'
import { ContextPanelProvider } from '@/lib/context-panel'
import { routeSearchFromDraft, type SearchRouteState } from '@/lib/search-route'

const SearchPage = lazy(() =>
  import('@/components/SearchPage').then((module) => ({ default: module.SearchPage })),
)
const ProjectDashboard = lazy(() =>
  import('@/components/ProjectDashboard').then((module) => ({
    default: module.ProjectDashboard,
  })),
)
const DocumentViewer = lazy(() =>
  import('@/components/DocumentViewer').then((module) => ({
    default: module.DocumentViewer,
  })),
)
const VersionHistory = lazy(() =>
  import('@/components/VersionHistory').then((module) => ({
    default: module.VersionHistory,
  })),
)
const ReviewInbox = lazy(() =>
  import('@/components/ReviewInbox').then((module) => ({
    default: module.ReviewInbox,
  })),
)

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
    },
  },
})

function RootComponent() {
  return (
    <ContextPanelProvider>
      <Layout>
        <Outlet />
      </Layout>
      <CommandPalette />
    </ContextPanelProvider>
  )
}

function HomeRouteComponent() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-2xl rounded-[2rem] border border-border/80 bg-card/70 p-10 shadow-sm">
        <div className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Phase 4
        </div>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight">
          Cabinet-first workspace for living project memory.
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-7 text-muted-foreground">
          Open a project from the cabinet, jump straight to search with
          <kbd className="mx-1 rounded border px-1.5 py-0.5 text-[11px]">/</kbd>
          , or use
          <kbd className="mx-1 rounded border px-1.5 py-0.5 text-[11px]">Ctrl+K</kbd>
          to navigate documents, dashboards, and search from anywhere.
        </p>
      </div>
    </div>
  )
}

function SearchRouteComponent() {
  const search = searchRoute.useSearch()
  const navigate = useNavigate()

  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading search…</div>}>
      <SearchPage
        routeSearch={search}
        navigateToSearch={(draft) =>
          navigate({
            to: '/search',
            search: routeSearchFromDraft(draft),
          })
        }
      />
    </Suspense>
  )
}

function ProjectLayoutRouteComponent() {
  return <Outlet />
}

function ProjectDashboardRouteComponent() {
  const { slug } = projectRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading dashboard…</div>}>
      <ProjectDashboard projectSlug={slug} />
    </Suspense>
  )
}

function ProjectDocsRouteComponent() {
  return <Outlet />
}

function DocumentRouteComponent() {
  const { slug, _splat } = documentRoute.useParams()
  const search = documentRoute.useSearch()
  if (!_splat) {
    return <div className="p-8 text-muted-foreground">Document path missing.</div>
  }

  if (_splat.endsWith('/history')) {
    const docPath = _splat.slice(0, -'/history'.length)
    return (
      <Suspense fallback={<div className="p-8 text-muted-foreground">Loading history…</div>}>
        <VersionHistory projectSlug={slug} docPath={docPath} />
      </Suspense>
    )
  }

  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading document…</div>}>
      <DocumentViewer
        projectSlug={slug}
        docPath={_splat}
        sourceContext={{
          query: search.sourceQuery,
          snippet: search.sourceSnippet,
          heading: search.sourceHeading,
          signals: search.sourceSignals ? search.sourceSignals.split(',').filter(Boolean) : [],
        }}
      />
    </Suspense>
  )
}

function ReviewInboxRouteComponent() {
  const { slug } = reviewInboxRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading review inbox…</div>}>
      <ReviewInbox projectSlug={slug} />
    </Suspense>
  )
}

const rootRoute = createRootRoute({
  component: RootComponent,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomeRouteComponent,
})

const searchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'search',
  validateSearch: (search: Record<string, unknown>): SearchRouteState => {
    const scope =
      search.scope === 'all' || search.scope === 'as_of' ? search.scope : 'current'
    const mode =
      search.mode === 'ask_question' ||
      search.mode === 'find_decisions' ||
      search.mode === 'search_history' ||
      search.mode === 'compare_over_time'
        ? search.mode
        : 'find_docs'
    const rawLimit =
      typeof search.limit === 'number'
        ? search.limit
        : typeof search.limit === 'string'
          ? Number(search.limit)
          : undefined

    const limit =
      typeof rawLimit === 'number' && Number.isFinite(rawLimit) && rawLimit > 0
        ? rawLimit
        : undefined

    return {
      query: typeof search.query === 'string' ? search.query : undefined,
      project: typeof search.project === 'string' ? search.project : undefined,
      mode,
      scope,
      as_of: typeof search.as_of === 'string' ? search.as_of : undefined,
      limit,
    }
  },
  component: SearchRouteComponent,
})

const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'projects/$slug',
  component: ProjectLayoutRouteComponent,
})

const projectIndexRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: '/',
  component: ProjectDashboardRouteComponent,
})

const projectDocsRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'docs',
  component: ProjectDocsRouteComponent,
})

const documentRoute = createRoute({
  getParentRoute: () => projectDocsRoute,
  path: '$',
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    sourceQuery?: string
    sourceSnippet?: string
    sourceHeading?: string
    sourceSignals?: string
  } => ({
    sourceQuery: typeof search.sourceQuery === 'string' ? search.sourceQuery : undefined,
    sourceSnippet: typeof search.sourceSnippet === 'string' ? search.sourceSnippet : undefined,
    sourceHeading: typeof search.sourceHeading === 'string' ? search.sourceHeading : undefined,
    sourceSignals: typeof search.sourceSignals === 'string' ? search.sourceSignals : undefined,
  }),
  component: DocumentRouteComponent,
})

const reviewInboxRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'review',
  component: ReviewInboxRouteComponent,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  searchRoute,
  projectRoute.addChildren([
    projectIndexRoute,
    reviewInboxRoute,
    projectDocsRoute.addChildren([
      documentRoute,
    ]),
  ]),
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  scrollRestoration: true,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
