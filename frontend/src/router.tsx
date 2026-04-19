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
import { ProjectCreationProvider } from '@/lib/project-creation'
import { routeSearchFromDraft, type SearchRouteState } from '@/lib/search-route'

const SearchPage = lazy(() =>
  import('@/components/SearchPage').then((module) => ({ default: module.SearchPage })),
)
const ProjectsHome = lazy(() =>
  import('@/components/ProjectsHome').then((module) => ({ default: module.ProjectsHome })),
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
const EntityExplorer = lazy(() =>
  import('@/components/EntityExplorer').then((module) => ({
    default: module.EntityExplorer,
  })),
)
const SessionsView = lazy(() =>
  import('@/components/SessionsView').then((module) => ({
    default: module.SessionsView,
  })),
)
const ProjectSettings = lazy(() =>
  import('@/components/ProjectSettings').then((module) => ({
    default: module.ProjectSettings,
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
      <ProjectCreationProvider>
        <Layout>
          <Outlet />
        </Layout>
        <CommandPalette />
      </ProjectCreationProvider>
    </ContextPanelProvider>
  )
}

function HomeRouteComponent() {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading projects…</div>}>
      <ProjectsHome />
    </Suspense>
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
          queryLabel: search.sourceQueryLabel,
          snippet: search.sourceSnippet,
          heading: search.sourceHeading,
          signals: search.sourceSignals ? search.sourceSignals.split(',').filter(Boolean) : [],
          versionNumber: search.sourceVersion,
          startChar: search.sourceStart,
          endChar: search.sourceEnd,
          chunkId: search.sourceChunkId,
        }}
      />
    </Suspense>
  )
}

function renderReviewInbox(slug: string) {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading review inbox…</div>}>
      <ReviewInbox projectSlug={slug} />
    </Suspense>
  )
}

function InboxRouteComponent() {
  const { slug } = inboxRoute.useParams()
  return renderReviewInbox(slug)
}

function LegacyReviewRouteComponent() {
  const { slug } = reviewAliasRoute.useParams()
  return renderReviewInbox(slug)
}

function EntitiesRouteComponent() {
  const { slug } = entitiesRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading entities…</div>}>
      <EntityExplorer projectSlug={slug} />
    </Suspense>
  )
}

function EntityDetailRouteComponent() {
  const { slug, entityId } = entityDetailRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading entity…</div>}>
      <EntityExplorer projectSlug={slug} entityId={entityId} />
    </Suspense>
  )
}

function SessionsRouteComponent() {
  const { slug } = sessionsRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading sessions…</div>}>
      <SessionsView projectSlug={slug} />
    </Suspense>
  )
}

function ProjectSettingsRouteComponent() {
  const { slug } = settingsRoute.useParams()
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading settings…</div>}>
      <ProjectSettings projectSlug={slug} />
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
      search.scope === 'all' ||
      search.scope === 'as_of' ||
      search.scope === 'snapshot' ||
      search.scope === 'branch'
        ? search.scope
        : 'current'
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
      snapshot: typeof search.snapshot === 'string' ? search.snapshot : undefined,
      branch: typeof search.branch === 'string' ? search.branch : undefined,
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
    sourceQueryLabel?: string
    sourceSnippet?: string
    sourceHeading?: string
    sourceSignals?: string
    sourceVersion?: number
    sourceStart?: number
    sourceEnd?: number
    sourceChunkId?: string
  } => ({
    sourceQuery: typeof search.sourceQuery === 'string' ? search.sourceQuery : undefined,
    sourceQueryLabel:
      typeof search.sourceQueryLabel === 'string' ? search.sourceQueryLabel : undefined,
    sourceSnippet: typeof search.sourceSnippet === 'string' ? search.sourceSnippet : undefined,
    sourceHeading: typeof search.sourceHeading === 'string' ? search.sourceHeading : undefined,
    sourceSignals: typeof search.sourceSignals === 'string' ? search.sourceSignals : undefined,
    sourceVersion:
      typeof search.sourceVersion === 'number'
        ? search.sourceVersion
        : typeof search.sourceVersion === 'string'
          ? Number(search.sourceVersion)
          : undefined,
    sourceStart:
      typeof search.sourceStart === 'number'
        ? search.sourceStart
        : typeof search.sourceStart === 'string'
          ? Number(search.sourceStart)
          : undefined,
    sourceEnd:
      typeof search.sourceEnd === 'number'
        ? search.sourceEnd
        : typeof search.sourceEnd === 'string'
          ? Number(search.sourceEnd)
          : undefined,
    sourceChunkId:
      typeof search.sourceChunkId === 'string' ? search.sourceChunkId : undefined,
  }),
  component: DocumentRouteComponent,
})

const inboxRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'inbox',
  component: InboxRouteComponent,
})

const reviewAliasRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'review',
  component: LegacyReviewRouteComponent,
})

const entitiesRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'entities',
  component: EntitiesRouteComponent,
})

const entityDetailRoute = createRoute({
  getParentRoute: () => entitiesRoute,
  path: '$entityId',
  component: EntityDetailRouteComponent,
})

const sessionsRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'sessions',
  component: SessionsRouteComponent,
})

const settingsRoute = createRoute({
  getParentRoute: () => projectRoute,
  path: 'settings',
  component: ProjectSettingsRouteComponent,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  searchRoute,
  projectRoute.addChildren([
    projectIndexRoute,
    inboxRoute,
    reviewAliasRoute,
    sessionsRoute,
    settingsRoute,
    entitiesRoute.addChildren([entityDetailRoute]),
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
