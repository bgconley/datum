import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Activity, AlertTriangle, Files, FolderKanban, Sparkles, Waypoints } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useContextPanel } from '@/lib/context-panel'
import { api, type Candidate, type DocumentMeta, type Project } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

function sortByRecency(documents: DocumentMeta[]) {
  return [...documents].sort((left, right) =>
    (right.updated || right.created || '').localeCompare(left.updated || left.created || ''),
  )
}

function buildAttentionAlerts(documents: DocumentMeta[], pendingCandidateCount: number) {
  const alerts: string[] = []
  const draftCount = documents.filter((document) => document.status === 'draft').length
  const decisionCount = documents.filter((document) => document.doc_type === 'decision').length
  const staleDocs = documents.filter((document) => {
    const dateValue = document.updated || document.created
    if (!dateValue) {
      return true
    }
    return Date.now() - new Date(dateValue).getTime() > 1000 * 60 * 60 * 24 * 14
  })

  if (draftCount > 0) {
    alerts.push(`${draftCount} document${draftCount === 1 ? '' : 's'} still in draft`)
  }
  if (decisionCount === 0) {
    alerts.push('No decision records yet')
  }
  if (staleDocs.length > 0) {
    alerts.push(`${staleDocs.length} document${staleDocs.length === 1 ? '' : 's'} look stale`)
  }
  if (pendingCandidateCount > 0) {
    alerts.push(`${pendingCandidateCount} inbox item${pendingCandidateCount === 1 ? '' : 's'} need review`)
  }
  if (documents.length === 0) {
    alerts.push('Project has no cabinet documents yet')
  }

  return alerts
}

function DashboardContextPanel({
  project,
  documents,
  keyEntities,
  pendingCandidateCount,
}: {
  project: Project
  documents: DocumentMeta[]
  keyEntities: string[]
  pendingCandidateCount: number
}) {
  const byType = documents.reduce<Record<string, number>>((accumulator, document) => {
    accumulator[document.doc_type] = (accumulator[document.doc_type] ?? 0) + 1
    return accumulator
  }, {})

  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Project context
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">{project.name}</h2>
        {project.description && (
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{project.description}</p>
        )}
      </div>

      <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Snapshot
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-muted-foreground">Status</div>
            <div className="mt-1 font-medium">{project.status}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Documents</div>
            <div className="mt-1 font-medium">{documents.length}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Inbox</div>
            <div className="mt-1 font-medium">{pendingCandidateCount}</div>
          </div>
        </div>
      </div>

      {project.tags.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Tags
          </div>
          <div className="flex flex-wrap gap-2">
            {project.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {keyEntities.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Key entities
          </div>
          <div className="flex flex-wrap gap-2">
            {keyEntities.map((entity) => (
              <Badge key={entity} variant="secondary">
                {entity}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <Separator />

      <div className="space-y-2">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Document mix
        </div>
        <div className="space-y-2">
          {Object.entries(byType).map(([type, count]) => (
            <div key={type} className="flex items-center justify-between text-sm">
              <span>{type}</span>
              <Badge variant="secondary">{count}</Badge>
            </div>
          ))}
          {Object.keys(byType).length === 0 && (
            <div className="text-sm text-muted-foreground">No document types yet.</div>
          )}
        </div>
      </div>
    </div>
  )
}

interface ProjectDashboardProps {
  projectSlug: string
}

const EMPTY_DOCUMENTS: DocumentMeta[] = []
const EMPTY_ENTITIES: string[] = []
const EMPTY_CANDIDATES: Candidate[] = []

export function ProjectDashboard({ projectSlug }: ProjectDashboardProps) {
  const { setContent } = useContextPanel()
  const workspaceQuery = useProjectWorkspaceQuery(projectSlug)
  const project = workspaceQuery.data?.project ?? null
  const documents = workspaceQuery.data?.documents ?? EMPTY_DOCUMENTS
  const intelligenceQuery = useQuery({
    queryKey: queryKeys.intelligenceSummary(projectSlug),
    queryFn: () => api.intelligence.summary(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const inboxQuery = useQuery({
    queryKey: queryKeys.inbox(projectSlug),
    queryFn: () => api.inbox.list(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const keyEntities =
    intelligenceQuery.data?.key_entities.map((entity) => entity.canonical_name) ?? EMPTY_ENTITIES
  const pendingCandidateCount = intelligenceQuery.data?.pending_candidate_count ?? 0
  const inboxCandidates = inboxQuery.data ?? EMPTY_CANDIDATES

  useEffect(() => {
    if (project) {
      setContent(
        <DashboardContextPanel
          project={project}
          documents={documents}
          keyEntities={keyEntities}
          pendingCandidateCount={pendingCandidateCount}
        />,
      )
    }
    return () => setContent(null)
  }, [documents, keyEntities, pendingCandidateCount, project, setContent])

  if (workspaceQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading project dashboard…</div>
  }

  if (!project) {
    return <div className="p-8 text-muted-foreground">Project not found.</div>
  }

  const recentDocuments = sortByRecency(documents).slice(0, 5)
  const byType = documents.reduce<Record<string, number>>((accumulator, document) => {
    accumulator[document.doc_type] = (accumulator[document.doc_type] ?? 0) + 1
    return accumulator
  }, {})
  const alerts = buildAttentionAlerts(documents, pendingCandidateCount)
  const decisionCandidates = inboxCandidates
    .filter((candidate) => candidate.candidate_type === 'decision')
    .slice(0, 5)
  const openQuestionCandidates = inboxCandidates
    .filter((candidate) => candidate.candidate_type === 'open_question')
    .slice(0, 5)
  const decisionDocs = documents.filter((document) => document.doc_type === 'decision').slice(0, 5)

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Project dashboard
        </div>
        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">{project.name}</h1>
            {project.description && (
              <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
                {project.description}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{project.status}</Badge>
            <Badge variant="secondary">{documents.length} docs</Badge>
            {pendingCandidateCount > 0 && <Badge variant="outline">{pendingCandidateCount} inbox</Badge>}
            {project.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="grid gap-6">
          <Card className="bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="size-4" />
                Recent activity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentDocuments.length === 0 ? (
                <div className="text-sm text-muted-foreground">No documents yet.</div>
              ) : (
                recentDocuments.map((document) => (
                  <Link
                    key={document.relative_path}
                    to="/projects/$slug/docs/$"
                    params={{ slug: projectSlug, _splat: document.relative_path }}
                    className="block rounded-2xl border border-border/70 bg-background/70 px-4 py-3 transition-colors hover:bg-accent/50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-medium">{document.title}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {document.relative_path}
                        </div>
                      </div>
                      <Badge variant="outline">v{document.version}</Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Updated {document.updated || document.created || 'unknown'}
                    </div>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="bg-card/80">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Waypoints className="size-4" />
                  Decisions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {decisionDocs.length === 0 && decisionCandidates.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No recorded decisions yet.</div>
                ) : (
                  <>
                    {decisionDocs.map((document) => (
                      <Link
                        key={document.relative_path}
                        to="/projects/$slug/docs/$"
                        params={{ slug: projectSlug, _splat: document.relative_path }}
                        className="block rounded-xl border border-border/70 bg-background/70 px-3 py-3 text-sm transition-colors hover:bg-accent/50"
                      >
                        {document.title}
                      </Link>
                    ))}
                    {decisionDocs.length === 0 &&
                      decisionCandidates.map((candidate) => (
                        <Link
                          key={candidate.id}
                          to="/projects/$slug/inbox"
                          params={{ slug: projectSlug }}
                          className="block rounded-xl border border-dashed border-border/70 bg-background/70 px-3 py-3 text-sm transition-colors hover:bg-accent/50"
                        >
                          {candidate.title}
                        </Link>
                      ))}
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="bg-card/80">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FolderKanban className="size-4" />
                  Open questions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {openQuestionCandidates.length === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    No open questions surfaced from the intelligence layer yet.
                  </div>
                ) : (
                  openQuestionCandidates.map((candidate) => (
                    <Link
                      key={candidate.id}
                      to="/projects/$slug/inbox"
                      params={{ slug: projectSlug }}
                      className="block rounded-xl border border-border/70 bg-background/70 px-3 py-3 text-sm transition-colors hover:bg-accent/50"
                    >
                      {candidate.title}
                    </Link>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="grid gap-6">
          <Card className="bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-4" />
                Key entities
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {keyEntities.length === 0 ? (
                <div className="text-sm text-muted-foreground">No entities surfaced yet.</div>
              ) : (
                keyEntities.map((entity) => (
                  <Link
                    key={entity}
                    to="/search"
                    search={{ query: entity, project: projectSlug }}
                    className="inline-flex items-center rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs transition-colors hover:bg-accent"
                  >
                    {entity}
                  </Link>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Files className="size-4" />
                Documents by type
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(byType).length === 0 ? (
                <div className="text-sm text-muted-foreground">No documents yet.</div>
              ) : (
                Object.entries(byType)
                  .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
                  .map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between text-sm">
                      <span>{type}</span>
                      <Badge variant="secondary">{count}</Badge>
                    </div>
                  ))
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/80">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="size-4" />
                Attention
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {alerts.length === 0 ? (
                <div className="text-sm text-muted-foreground">No alerts. Cabinet state looks healthy.</div>
              ) : (
                alerts.map((alert) => (
                  <div
                    key={alert}
                    className="rounded-2xl border border-border/70 bg-background/70 px-4 py-3 text-sm"
                  >
                    {alert}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
