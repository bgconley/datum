import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileText,
  FolderOpen,
  Layers,
  Terminal,
  Zap,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useContextPanel } from '@/lib/context-panel'
import {
  api,
  type ActivityEvent,
  type Candidate,
  type DocumentMeta,
  type HealthResponse,
  type HealthSubsystem,
  type IngestionStats,
  type AgentActivityStats,
  type OpenQuestionSummary,
  type Project,
  type SessionSummary,
} from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

/* ---------- helpers ---------- */

const SECTION_HEADER =
  'text-[11px] font-semibold uppercase tracking-widest text-muted-foreground'

const INFRASTRUCTURE_SUBSYSTEMS = ['zfs_pool', 'paradedb', 'file_watcher', 'worker_queue']
const MODEL_SUBSYSTEMS = ['embedder', 'reranker', 'gliner_ner', 'llm']

function subsystemLabel(name: string): string {
  const map: Record<string, string> = {
    zfs_pool: 'ZFS Pool',
    paradedb: 'ParadeDB',
    file_watcher: 'File Watcher',
    worker_queue: 'Worker Queue',
    embedder: 'Embedder',
    reranker: 'Reranker',
    gliner_ner: 'GLiNER NER',
    llm: 'LLM',
  }
  return map[name] ?? name
}

function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <span
      className={`inline-block size-2 rounded-full ${healthy ? 'bg-green-500' : 'bg-red-500'}`}
    />
  )
}

function subsystemsByGroup(
  subsystems: HealthSubsystem[],
  names: string[],
): HealthSubsystem[] {
  const byName = new Map(subsystems.map((s) => [s.name, s]))
  return names
    .map((n) => byName.get(n))
    .filter((s): s is HealthSubsystem => s !== undefined)
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function activityIcon(operation: string) {
  if (operation.includes('create') || operation.includes('ingest'))
    return <FileText className="size-3.5 text-[#22A5F1]" />
  if (operation.includes('update') || operation.includes('save'))
    return <Layers className="size-3.5 text-amber-500" />
  if (operation.includes('delete'))
    return <AlertTriangle className="size-3.5 text-red-500" />
  if (operation.includes('session') || operation.includes('hook'))
    return <Terminal className="size-3.5 text-green-600" />
  return <Activity className="size-3.5 text-muted-foreground" />
}

function activityLabel(event: ActivityEvent): string {
  const op = event.operation.replaceAll('_', ' ')
  const target = event.target_path
    ? event.target_path.split('/').pop() ?? event.target_path
    : null
  if (target) return `${op} - ${target}`
  return op
}

function buildAttentionAlerts(
  documents: DocumentMeta[],
  pendingCandidateCount: number,
  openQuestions: OpenQuestionSummary[],
) {
  const alerts: { label: string; count?: number }[] = []
  const staleDocs = documents.filter((doc) => {
    const dateValue = doc.updated || doc.created
    if (!dateValue) return true
    return Date.now() - new Date(dateValue).getTime() > 1000 * 60 * 60 * 24 * 14
  })

  if (staleDocs.length > 0) {
    alerts.push({
      label: `${staleDocs.length} document${staleDocs.length === 1 ? '' : 's'} look stale`,
    })
  }
  const agedOpenQuestions = openQuestions.filter((q) => q.is_stale)
  if (agedOpenQuestions.length > 0) {
    alerts.push({
      label: `${agedOpenQuestions.length} open question${agedOpenQuestions.length === 1 ? '' : 's'} older than 30 days`,
    })
  }
  if (pendingCandidateCount > 0) {
    alerts.push({
      label: `${pendingCandidateCount} inbox item${pendingCandidateCount === 1 ? '' : 's'} need review`,
    })
  }

  return alerts
}

/* ---------- widgets ---------- */

function SystemHealthWidget({ health }: { health: HealthResponse | undefined }) {
  const subsystems = health?.subsystems ?? []
  const infra = subsystemsByGroup(subsystems, INFRASTRUCTURE_SUBSYSTEMS)
  const models = subsystemsByGroup(subsystems, MODEL_SUBSYSTEMS)
  const allHealthy = health?.healthy ?? true

  return (
    <Card>
      <CardContent className="pt-1">
        <div className="flex items-center justify-between">
          <h3 className={SECTION_HEADER}>Datum System Health</h3>
          <Badge
            variant={allHealthy ? 'default' : 'destructive'}
            className={
              allHealthy
                ? 'bg-green-100 text-green-700 border-green-200'
                : undefined
            }
          >
            <CheckCircle2 className="mr-1 size-3" />
            {allHealthy ? 'ALL SYSTEMS OPERATIONAL' : 'DEGRADED'}
          </Badge>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-6">
          {/* Infrastructure column */}
          <div>
            <div className={SECTION_HEADER}>Infrastructure</div>
            <div className="mt-2 space-y-2">
              {infra.map((sub) => (
                <div key={sub.name} className="flex items-center gap-2 text-sm">
                  <StatusDot healthy={sub.healthy} />
                  <span>{subsystemLabel(sub.name)}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {sub.healthy ? 'Healthy' : sub.error ?? 'Error'}
                  </span>
                </div>
              ))}
              {infra.length === 0 && (
                <div className="text-sm text-muted-foreground">No data</div>
              )}
            </div>
          </div>

          {/* Model services column */}
          <div>
            <div className={SECTION_HEADER}>Model Services</div>
            <div className="mt-2 space-y-2">
              {models.map((sub) => (
                <div key={sub.name} className="flex items-center gap-2 text-sm">
                  <StatusDot healthy={sub.healthy} />
                  <span>{subsystemLabel(sub.name)}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {sub.healthy
                      ? sub.latency_ms !== null
                        ? `${sub.latency_ms}ms`
                        : 'Healthy'
                      : sub.error ?? 'Error'}
                  </span>
                </div>
              ))}
              {models.length === 0 && (
                <div className="text-sm text-muted-foreground">No data</div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function IngestionBar({ stats }: { stats: IngestionStats | undefined }) {
  if (!stats) return null
  return (
    <div className="mt-3 flex items-center gap-4 rounded border border-border bg-muted px-4 py-2 text-sm">
      <span className={SECTION_HEADER}>Ingestion</span>
      <span>
        <span className="font-medium">{stats.queued}</span>{' '}
        <span className="text-muted-foreground">queued</span>
      </span>
      <span className="text-muted-foreground">·</span>
      <span>
        <span className="font-medium">{stats.processing}</span>{' '}
        <span className="text-muted-foreground">running</span>
      </span>
      <span className="text-muted-foreground">·</span>
      <span>
        <span className="font-medium">{stats.failed}</span>{' '}
        <span className="text-muted-foreground">failed</span>
      </span>
    </div>
  )
}

function KnowledgeSummaryWidget({
  projectCount,
  docCount,
  entityCount,
}: {
  projectCount: number
  docCount: number
  entityCount: number
}) {
  return (
    <Card>
      <CardContent className="pt-1">
        <h3 className={SECTION_HEADER}>Knowledge Summary</h3>
        <div className="mt-4 flex items-baseline gap-3">
          <div>
            <span className="text-3xl font-bold tracking-tight">{projectCount}</span>
            <span className="ml-1.5 text-xs font-medium uppercase text-muted-foreground">
              Projects
            </span>
          </div>
          <span className="text-muted-foreground">·</span>
          <div>
            <span className="text-3xl font-bold tracking-tight">{docCount}</span>
            <span className="ml-1.5 text-xs font-medium uppercase text-muted-foreground">
              Documents
            </span>
          </div>
          <span className="text-muted-foreground">·</span>
          <div>
            <span className="text-3xl font-bold tracking-tight">{entityCount}</span>
            <span className="ml-1.5 text-xs font-medium uppercase text-muted-foreground">
              Entities
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function AttentionAlertsWidget({
  candidateCount,
  alerts,
  projectSlug,
}: {
  candidateCount: number
  alerts: { label: string }[]
  projectSlug: string
}) {
  return (
    <Card>
      <CardContent className="pt-1">
        <h3 className={SECTION_HEADER}>Attention Alerts</h3>
        <div className="mt-4">
          {candidateCount > 0 ? (
            <Link
              to="/projects/$slug/inbox"
              params={{ slug: projectSlug }}
              className="group flex items-center gap-2"
            >
              <span className="text-2xl font-bold tracking-tight text-amber-600">
                {candidateCount}
              </span>
              <span className="text-sm font-medium uppercase text-amber-600 group-hover:underline">
                Candidates for Review
              </span>
            </Link>
          ) : (
            <div className="text-sm text-muted-foreground">No candidates pending</div>
          )}
          {alerts.length > 0 && (
            <ul className="mt-3 space-y-1">
              {alerts.map((alert) => (
                <li
                  key={alert.label}
                  className="flex items-start gap-2 text-sm text-muted-foreground"
                >
                  <Circle className="mt-1 size-1.5 shrink-0 fill-current" />
                  {alert.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function AgentActivityWidget({
  activity,
  sessions,
  projectSlug,
}: {
  activity: AgentActivityStats | undefined
  sessions: SessionSummary[] | undefined
  projectSlug: string
}) {
  const sessionList = sessions ?? []
  const finalizedCount = sessionList.filter(
    (s) => s.status === 'finalized' || (s.ended_at && !s.is_dirty),
  ).length
  const dirtyCount = sessionList.filter((s) => s.is_dirty).length
  const activeCount = sessionList.filter(
    (s) => s.status === 'active' && !s.ended_at,
  ).length

  const hookEvents = activity?.hook_event_counts ?? {}
  const mcpOps = activity?.mcp_op_counts ?? {}

  const hookOrder = ['SessionStart', 'PreToolUse', 'PostToolUse', 'PreCompact', 'Stop']
  const sortedHooks = hookOrder
    .filter((h) => h in hookEvents)
    .map((h) => [h, hookEvents[h]] as const)
  const remainingHooks = Object.entries(hookEvents).filter(
    ([k]) => !hookOrder.includes(k),
  )

  return (
    <Card>
      <CardContent className="pt-1">
        <h3 className={SECTION_HEADER}>Agent Activity (24h)</h3>

        {/* Session status row */}
        <div className="mt-4 flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {finalizedCount > 0 && (
              <div className="flex items-center gap-1 text-sm">
                <span className="inline-block size-2 rounded-full bg-green-500" />
                <span>{finalizedCount} finalized</span>
              </div>
            )}
            {dirtyCount > 0 && (
              <div className="flex items-center gap-1 text-sm">
                <span className="inline-block size-2 rounded-full bg-amber-500" />
                <span>{dirtyCount} dirty</span>
              </div>
            )}
            {activeCount > 0 && (
              <div className="flex items-center gap-1 text-sm">
                <span className="inline-block size-2 rounded-full bg-[#22A5F1]" />
                <span>{activeCount} active</span>
              </div>
            )}
          </div>
          <Badge className="bg-[#22A5F1] text-white border-transparent">
            {sessionList.length} Sessions
          </Badge>
        </div>

        {/* Hook events */}
        {(sortedHooks.length > 0 || remainingHooks.length > 0) && (
          <div className="mt-4">
            <div className={SECTION_HEADER}>Hook Events</div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {[...sortedHooks, ...remainingHooks].map(([hook, count]) => (
                <div key={hook} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{hook}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MCP tool calls */}
        {Object.keys(mcpOps).length > 0 && (
          <div className="mt-4">
            <div className={SECTION_HEADER}>MCP Tool Calls</div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {Object.entries(mcpOps)
                .sort(([, a], [, b]) => b - a)
                .map(([op, count]) => (
                  <div key={op} className="flex items-center justify-between">
                    <span className="text-muted-foreground">{op}</span>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        <div className="mt-4">
          <Link
            to="/projects/$slug/sessions"
            params={{ slug: projectSlug }}
            className="text-sm font-medium text-[#22A5F1] hover:underline"
          >
            View All Sessions &rarr;
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

function RecentActivityWidget({
  events,
}: {
  events: ActivityEvent[]
}) {
  return (
    <Card>
      <CardContent className="pt-1">
        <h3 className={SECTION_HEADER}>Recent Activity</h3>
        {events.length === 0 ? (
          <div className="mt-4 text-sm text-muted-foreground">No recent activity.</div>
        ) : (
          <div className="mt-4 space-y-3">
            {events.map((event) => (
              <div key={event.id} className="flex items-start gap-3">
                <div className="mt-0.5">{activityIcon(event.operation)}</div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {activityLabel(event)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {event.actor_type} · {formatTimestamp(event.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/* ---------- context panel ---------- */

function DashboardContextPanel({
  project,
  documents,
  pendingCandidateCount,
  openQuestionCount,
  staleDocs,
  health,
}: {
  project: Project
  documents: DocumentMeta[]
  pendingCandidateCount: number
  openQuestionCount: number
  staleDocs: number
  health: HealthResponse | undefined
}) {
  const subsystems = health?.subsystems ?? []
  const zfsSub = subsystems.find((s) => s.name === 'zfs_pool')

  return (
    <div className="space-y-5 p-5">
      {/* Header */}
      <div>
        <div className={SECTION_HEADER}>Context: Project</div>
        <h2 className="mt-2 text-lg font-semibold tracking-tight">{project.name}</h2>
      </div>

      {/* Status / Path / Updated / Tags */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Status</span>
          <Badge
            variant="default"
            className="bg-green-100 text-green-700 border-green-200"
          >
            {project.status.toUpperCase()}
          </Badge>
        </div>
        {project.filesystem_path && (
          <div className="flex items-start justify-between gap-3 text-sm">
            <span className="shrink-0 text-muted-foreground">ZFS Path</span>
            <span className="truncate text-right font-mono text-xs">
              {project.filesystem_path}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Updated</span>
          <span>
            {documents.length > 0
              ? formatTimestamp(
                  [...documents]
                    .sort((a, b) =>
                      (b.updated || b.created || '').localeCompare(
                        a.updated || a.created || '',
                      ),
                    )[0].updated ??
                    documents[0].created ??
                    '',
                )
              : 'N/A'}
          </span>
        </div>
        {project.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {project.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Intelligence Summary */}
      <div>
        <div className={SECTION_HEADER}>Intelligence Summary</div>
        <div className="mt-3 space-y-2">
          {pendingCandidateCount > 0 && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
              {pendingCandidateCount} Candidate{pendingCandidateCount === 1 ? '' : 's'}{' '}
              for Review
            </div>
          )}
          <ul className="space-y-1 text-sm text-muted-foreground">
            {staleDocs > 0 && (
              <li className="flex items-start gap-2">
                <Circle className="mt-1 size-1.5 shrink-0 fill-current" />
                {staleDocs} stale document{staleDocs === 1 ? '' : 's'}
              </li>
            )}
            {openQuestionCount > 0 && (
              <li className="flex items-start gap-2">
                <Circle className="mt-1 size-1.5 shrink-0 fill-current" />
                {openQuestionCount} open question{openQuestionCount === 1 ? '' : 's'}
              </li>
            )}
            {pendingCandidateCount === 0 &&
              staleDocs === 0 &&
              openQuestionCount === 0 && (
                <li className="text-green-600">All clear</li>
              )}
          </ul>
        </div>
      </div>

      <Separator />

      {/* System Health */}
      <div>
        <div className={SECTION_HEADER}>System Health</div>
        <div className="mt-3 space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">ZFS Snapshots</span>
            <span>{zfsSub?.healthy ? 'OK' : 'Unknown'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Disk Usage</span>
            <span>{zfsSub?.healthy ? 'Healthy' : 'Unknown'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ---------- main component ---------- */

interface ProjectDashboardProps {
  projectSlug: string
}

const EMPTY_DOCUMENTS: DocumentMeta[] = []
const EMPTY_CANDIDATES: Candidate[] = []
const EMPTY_OPEN_QUESTIONS: OpenQuestionSummary[] = []

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

  const healthQuery = useQuery({
    queryKey: queryKeys.dashboardHealth,
    queryFn: () => api.dashboard.health(),
    refetchInterval: 15_000,
  })

  const ingestionQuery = useQuery({
    queryKey: queryKeys.dashboardIngestion(projectSlug),
    queryFn: () => api.dashboard.ingestion(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 10_000,
  })

  const agentActivityQuery = useQuery({
    queryKey: queryKeys.agentActivity(projectSlug),
    queryFn: () => api.dashboard.agentActivity(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 30_000,
  })

  const activityQuery = useQuery({
    queryKey: queryKeys.dashboardActivity(projectSlug),
    queryFn: () => api.dashboard.activity(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 15_000,
  })

  const sessionsQuery = useQuery({
    queryKey: queryKeys.dashboardSessions(projectSlug),
    queryFn: () => api.dashboard.sessions(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 30_000,
  })

  const pendingCandidateCount = intelligenceQuery.data?.pending_candidate_count ?? 0
  const inboxCandidates = inboxQuery.data ?? EMPTY_CANDIDATES
  const openQuestions =
    intelligenceQuery.data?.open_questions ?? EMPTY_OPEN_QUESTIONS
  const keyEntities = intelligenceQuery.data?.key_entities ?? []
  const entityCount = keyEntities.reduce((sum, e) => sum + e.count, 0)
  const staleDocs = documents.filter((doc) => {
    const dateValue = doc.updated || doc.created
    if (!dateValue) return true
    return Date.now() - new Date(dateValue).getTime() > 1000 * 60 * 60 * 24 * 14
  })

  const alerts = buildAttentionAlerts(documents, pendingCandidateCount, openQuestions)

  // Context panel
  useEffect(() => {
    if (project) {
      setContent(
        <DashboardContextPanel
          project={project}
          documents={documents}
          pendingCandidateCount={pendingCandidateCount}
          openQuestionCount={openQuestions.length}
          staleDocs={staleDocs.length}
          health={healthQuery.data}
        />,
      )
    }
    return () => setContent(null)
  }, [
    documents,
    healthQuery.data,
    openQuestions,
    pendingCandidateCount,
    project,
    setContent,
    staleDocs.length,
  ])

  if (workspaceQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading project dashboard...</div>
  }

  if (!project) {
    return <div className="p-8 text-muted-foreground">Project not found.</div>
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5 p-6">
      {/* Page title */}
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      {/* System Health (full width) */}
      <div>
        <SystemHealthWidget health={healthQuery.data} />
        <IngestionBar stats={ingestionQuery.data} />
      </div>

      {/* Knowledge Summary + Attention Alerts (2-column) */}
      <div className="grid gap-5 lg:grid-cols-2">
        <KnowledgeSummaryWidget
          projectCount={1}
          docCount={documents.length}
          entityCount={entityCount}
        />
        <AttentionAlertsWidget
          candidateCount={pendingCandidateCount}
          alerts={alerts}
          projectSlug={projectSlug}
        />
      </div>

      {/* Agent Activity + Recent Activity (2-column) */}
      <div className="grid gap-5 lg:grid-cols-2">
        <AgentActivityWidget
          activity={agentActivityQuery.data}
          sessions={sessionsQuery.data}
          projectSlug={projectSlug}
        />
        <RecentActivityWidget events={activityQuery.data ?? []} />
      </div>
    </div>
  )
}
