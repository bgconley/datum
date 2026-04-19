import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { openTemplateDialog } from '@/components/CreateDocumentDialog'
import { UploadModal } from '@/components/UploadModal'
import { useContextPanel } from '@/lib/context-panel'
import {
  api,
  type AttachmentItem,
  type ActivityEvent,
  type DocumentMeta,
  type GeneratedFile,
  type HealthSubsystem,
  type OpenQuestionSummary,
  type SessionSummary,
} from '@/lib/api'
import { isProjectOnboardingState } from '@/lib/project-onboarding'
import { queryKeys } from '@/lib/query-keys'
import { useProjectWorkspaceQuery } from '@/lib/workspace-query'

/* ── Figma-exact constants ── */

const CARD = 'bg-white border border-[#e1e8ed] rounded-[4px] px-[20px] py-[14px]'
const CARD_TITLE = 'text-[13px] font-semibold text-[#333]'
const SECTION_LABEL = 'text-[9px] font-semibold text-[#666]'
const DIVIDER = 'h-px w-full bg-[#e1e8ed]'
const DOT_GREEN = 'inline-block size-[8px] rounded-full bg-[#5cb85c]'
const DOT_AMBER = 'inline-block size-[8px] rounded-full bg-[#f0ad4e]'
const DOT_RED = 'inline-block size-[8px] rounded-full bg-[#d9534f]'
const DOT_BLUE = 'inline-block size-[8px] rounded-full bg-[#22a5f1]'
const DOT_BLACK = 'inline-block size-[8px] rounded-full bg-[#333]'

const INFRA_NAMES = ['zfs_pool', 'paradedb', 'file_watcher', 'worker_queue']
const MODEL_NAMES = ['embedder', 'reranker', 'gliner_ner', 'llm']

const LABELS: Record<string, string> = {
  zfs_pool: 'ZFS Pool',
  paradedb: 'ParadeDB',
  file_watcher: 'File Watcher',
  worker_queue: 'Worker Queue',
  embedder: 'Embedder (Qwen3-4B)',
  reranker: 'Reranker (Qwen3-0.6B)',
  gliner_ner: 'GLiNER NER',
  llm: 'LLM (GPT-OSS-20B)',
}

const FALLBACK_PORTS: Record<string, string> = {
  embedder: ':8010',
  reranker: ':8011',
  gliner_ner: ':8012',
  llm: ':8000',
}

function endpointPort(endpoint: string | null | undefined, name: string) {
  if (!endpoint) {
    return FALLBACK_PORTS[name] ?? ''
  }
  try {
    const parsed = new URL(endpoint)
    return parsed.port ? `:${parsed.port}` : FALLBACK_PORTS[name] ?? ''
  } catch {
    return FALLBACK_PORTS[name] ?? ''
  }
}

function dot(healthy: boolean) {
  return <span className={healthy ? DOT_GREEN : DOT_RED} />
}

function subsByGroup(all: HealthSubsystem[], names: string[]) {
  const m = new Map(all.map((s) => [s.name, s]))
  return names.map((n) => m.get(n)).filter((s): s is HealthSubsystem => !!s)
}

function infraStatus(s: HealthSubsystem) {
  if (!s.healthy) return 'Error'
  if (s.name === 'file_watcher') return 'Running'
  if (s.name === 'worker_queue') return s.error ?? '0 jobs'
  return 'OK'
}

function modelStatus(s: HealthSubsystem) {
  const port = endpointPort(s.endpoint, s.name)
  if (!s.healthy) return `Idle  ${port}`
  return `OK  ${port}`
}

function formatTime(iso: string) {
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60_000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m} min ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`
  return `${Math.floor(h / 24)} day${Math.floor(h / 24) === 1 ? '' : 's'} ago`
}

function opIcon(op: string) {
  if (op.includes('create')) return '📄'
  if (op.includes('update') || op.includes('save')) return '✎'
  if (op.includes('link')) return '🔗'
  if (op.includes('decision') || op.includes('promot')) return '✓'
  if (op.includes('upload') || op.includes('ingest')) return '📥'
  if (op.includes('reconcil')) return '⚡'
  if (op.includes('mkdir')) return '📁'
  return '•'
}

function opLabel(e: ActivityEvent) {
  const target = e.target_path?.split('/').pop() ?? e.target_path
  const op = e.operation.replaceAll('_', ' ')
  return target ? `${op} - ${target}` : op
}

function opColor(op: string) {
  if (op.includes('decision') || op.includes('promot')) return 'text-[#5cb85c]'
  if (op.includes('link')) return 'text-[#22a5f1]'
  return 'text-[#333]'
}

/* ── Dashboard component ── */

interface Props {
  projectSlug: string
}

const EMPTY_DOCS: DocumentMeta[] = []
const EMPTY_ATTACHMENTS: AttachmentItem[] = []
const EMPTY_GENERATED_FILES: GeneratedFile[] = []
const EMPTY_OQ: OpenQuestionSummary[] = []

export function ProjectDashboard({ projectSlug }: Props) {
  const { setContent } = useContextPanel()
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const wq = useProjectWorkspaceQuery(projectSlug)
  const project = wq.data?.project ?? null
  const docs = wq.data?.documents ?? EMPTY_DOCS
  const attachments = wq.data?.attachments ?? EMPTY_ATTACHMENTS
  const generatedFiles = wq.data?.generated_files ?? EMPTY_GENERATED_FILES

  const intQ = useQuery({
    queryKey: queryKeys.intelligenceSummary(projectSlug),
    queryFn: () => api.intelligence.summary(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const inboxQ = useQuery({
    queryKey: queryKeys.inbox(projectSlug),
    queryFn: () => api.inbox.list(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const healthQ = useQuery({
    queryKey: queryKeys.dashboardHealth,
    queryFn: () => api.dashboard.health(),
    refetchInterval: 15_000,
  })
  const ingQ = useQuery({
    queryKey: queryKeys.dashboardIngestion(projectSlug),
    queryFn: () => api.dashboard.ingestion(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 10_000,
  })
  const agentQ = useQuery({
    queryKey: queryKeys.agentActivity(projectSlug),
    queryFn: () => api.dashboard.agentActivity(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 30_000,
  })
  const actQ = useQuery({
    queryKey: queryKeys.dashboardActivity(projectSlug),
    queryFn: () => api.dashboard.activity(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 15_000,
  })
  const sessQ = useQuery({
    queryKey: queryKeys.dashboardSessions(projectSlug),
    queryFn: () => api.dashboard.sessions(projectSlug),
    enabled: Boolean(projectSlug),
    refetchInterval: 30_000,
  })

  const pendingCount = intQ.data?.pending_candidate_count ?? 0
  const openQuestions = intQ.data?.open_questions ?? EMPTY_OQ
  const entities = intQ.data?.key_entities ?? []
  const entityCount = entities.reduce((s, e) => s + e.count, 0)
  const staleDocs = useMemo(
    () =>
      docs.filter((d) => {
        const v = d.updated || d.created
        return !v || Date.now() - new Date(v).getTime() > 14 * 86_400_000
      }),
    [docs],
  )
  const health = healthQ.data
  const subs = health?.subsystems ?? []
  const infra = subsByGroup(subs, INFRA_NAMES)
  const models = subsByGroup(subs, MODEL_NAMES)
  const allHealthy = health?.healthy ?? true
  const ing = ingQ.data
  const agent = agentQ.data
  const sessions = sessQ.data ?? []
  const activity = actQ.data ?? []
  const showOnboarding = isProjectOnboardingState({
    attachmentsCount: attachments.length,
    documentsCount: docs.length,
    generatedFilePaths: generatedFiles.map((file) => file.relative_path),
    pendingCandidateCount: pendingCount,
    sessionCount: sessions.length,
  })

  const finalizedCount = sessions.filter((s) => s.status === 'finalized').length
  const dirtyCount = sessions.filter((s) => s.is_dirty).length
  const activeCount = sessions.filter((s) => s.status === 'active' && !s.ended_at).length
  const hookEvents = agent?.hook_event_counts ?? {}
  const mcpOps = agent?.mcp_op_counts ?? {}
  const hookOrder = ['SessionStart', 'PreToolUse', 'PostToolUse', 'PreCompact', 'Stop']

  // Context panel
  useEffect(() => {
    if (!project) return () => setContent(null)
    if (showOnboarding) {
      setContent(
        <div className="flex flex-col gap-[10px] p-[16px]">
          <p className={SECTION_LABEL}>CONTEXT: PROJECT</p>
          <div className={DIVIDER} />
          <div className="flex items-start justify-between text-[11px]">
            <span className="text-[#666]">Status</span>
            <span className="rounded-[3px] bg-[#5cb85c] px-[8px] py-[3px] text-[10px] font-semibold text-white">
              {project.status.toUpperCase()}
            </span>
          </div>
          <div className="flex items-start justify-between text-[11px]">
            <span className="text-[#666]">Created</span>
            <span className="font-medium text-[#333]">
              {project.created ? formatTime(project.created) : 'just now'}
            </span>
          </div>
          <div className="flex flex-wrap items-start gap-[6px]">
            <span className="text-[11px] text-[#666]">Tags</span>
            {project.tags.length > 0 ? (
              project.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-[#f3f6f8] px-[8px] py-[2px] text-[10px] font-medium text-[#1b2431]"
                >
                  {tag}
                </span>
              ))
            ) : (
              <span className="text-[11px] text-[#999]">No tags yet.</span>
            )}
          </div>
          <div className={DIVIDER} />
          <p className={SECTION_LABEL}>ONBOARDING CHECKLIST</p>
          <div className="space-y-[4px] text-[11px] text-[#333]">
            <p>• Upload first source document</p>
            <p>• Create a project brief</p>
            <p>• Run first grounded search</p>
          </div>
          <div className={DIVIDER} />
          <p className={SECTION_LABEL}>ROUTE BEHAVIOR</p>
          <p className="text-[11px] text-[#7b8794]">Preserve section context when possible.</p>
        </div>,
      )
      return () => setContent(null)
    }

    setContent(
      <div className="flex flex-col gap-[10px] p-[16px]">
        <p className={SECTION_LABEL}>CONTEXT: PROJECT</p>
        <div className={DIVIDER} />
        <div className="flex items-start justify-between">
          <span className="text-[11px] text-[#666]">Status</span>
          <span className="rounded-[3px] bg-[#5cb85c] px-[8px] py-[3px] text-[10px] font-semibold text-white">
            {project.status.toUpperCase()}
          </span>
        </div>
        {project.filesystem_path && (
          <div className="flex items-start justify-between text-[11px]">
            <span className="text-[#666]">ZFS Path</span>
            <span className="font-medium text-[#333]">{project.filesystem_path}</span>
          </div>
        )}
        <div className="flex items-start justify-between text-[11px]">
          <span className="text-[#666]">Updated</span>
          <span className="font-medium text-[#333]">
            {docs.length > 0
              ? new Date(
                  [...docs].sort((a, b) =>
                    (b.updated || b.created || '').localeCompare(a.updated || a.created || ''),
                  )[0].updated ?? docs[0].created ?? '',
                ).toLocaleDateString()
              : 'N/A'}
          </span>
        </div>
        {project.tags.length > 0 && (
          <div className="flex items-start gap-[6px]">
            <span className="text-[11px] text-[#666]">Tags:</span>
            {project.tags.map((t) => (
              <span key={t} className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[10px] font-semibold text-[#333]">
                {t}
              </span>
            ))}
          </div>
        )}
        <div className={DIVIDER} />
        <p className={SECTION_LABEL}>INTELLIGENCE SUMMARY</p>
        {pendingCount > 0 ? (
          <>
            <div className="rounded-[4px] bg-[#d9534f] px-[12px] py-[8px] text-[12px] font-semibold text-white">
              {pendingCount} Candidate{pendingCount === 1 ? '' : 's'} for Review
            </div>
            {openQuestions.length > 0 && (
              <div className="flex items-center gap-[8px]">
                <span className={DOT_BLUE} />
                <span className="text-[11px] text-[#333]">{openQuestions.length} Open Questions</span>
              </div>
            )}
            {staleDocs.length > 0 && (
              <div className="flex items-center gap-[8px]">
                <span className={DOT_AMBER} />
                <span className="text-[11px] text-[#333]">{staleDocs.length} Stale Documents</span>
              </div>
            )}
          </>
        ) : (
          <span className="text-[11px] text-[#5cb85c]">All clear</span>
        )}
        <div className={DIVIDER} />
        <p className={SECTION_LABEL}>SYSTEM HEALTH</p>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-[6px]">
            <span className={infra.find((s) => s.name === 'zfs_pool')?.healthy ? DOT_GREEN : DOT_RED} />
            <span className="text-[11px] text-[#666]">ZFS Snapshots</span>
          </div>
          <span className="text-[11px] font-medium text-[#333]">
            {infra.find((s) => s.name === 'zfs_pool')?.healthy ? 'OK' : 'Unknown'}
          </span>
        </div>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-[6px]">
            <span className={DOT_BLACK} />
            <span className="text-[11px] text-[#666]">Disk Usage</span>
          </div>
          <span className="text-[11px] font-medium text-[#333]">
            {infra.find((s) => s.name === 'zfs_pool')?.healthy ? 'Healthy' : 'Unknown'}
          </span>
        </div>
      </div>,
    )
    return () => setContent(null)
  }, [project, docs, pendingCount, openQuestions, staleDocs, showOnboarding, health, infra, setContent])

  if (wq.isLoading) {
    return <div className="p-8 text-[#666]">Loading project dashboard...</div>
  }
  if (!project) {
    return <div className="p-8 text-[#666]">Project not found.</div>
  }

  const systemHealthCard = (
    <div className={`${CARD} flex flex-col gap-[10px]`}>
      <div className="flex items-center justify-between">
        <span className={CARD_TITLE}>Datum System Health</span>
        <div className="flex items-center gap-[6px]">
          <span className={allHealthy ? DOT_GREEN : DOT_RED} />
          <span
            className={`text-[9px] font-semibold ${allHealthy ? 'text-[#5cb85c]' : 'text-[#d9534f]'}`}
          >
            {allHealthy ? 'ALL SYSTEMS OPERATIONAL' : 'DEGRADED'}
          </span>
        </div>
      </div>
      <div className={DIVIDER} />
      <div className="flex gap-[32px]">
        <div className="flex flex-1 flex-col gap-[5px]">
          <span className={SECTION_LABEL}>INFRASTRUCTURE</span>
          {infra.map((s) => (
            <div key={s.name} className="flex items-center justify-between">
              <div className="flex items-center gap-[6px]">
                {dot(s.healthy)}
                <span className="text-[11px] text-[#333]">{LABELS[s.name]}</span>
              </div>
              <span className="text-[11px] font-medium text-[#333]">{infraStatus(s)}</span>
            </div>
          ))}
          {infra.length === 0 && <span className="text-[11px] text-[#999]">No data</span>}
        </div>
        <div className="flex flex-1 flex-col gap-[5px]">
          <span className={SECTION_LABEL}>MODEL SERVICES</span>
          {models.map((s) => (
            <div key={s.name} className="flex items-center justify-between">
              <div className="flex items-center gap-[6px]">
                {dot(s.healthy)}
                <span className="text-[11px] text-[#333]">{LABELS[s.name]}</span>
              </div>
              <span className="whitespace-pre text-[11px] font-medium text-[#333]">
                {modelStatus(s)}
              </span>
            </div>
          ))}
          {models.length === 0 && <span className="text-[11px] text-[#999]">No data</span>}
        </div>
      </div>
      <div className={DIVIDER} />
      <div className="flex items-center gap-[12px]">
        <span className={SECTION_LABEL}>INGESTION:</span>
        <span className="text-[11px] text-[#333]">{ing?.queued ?? 0} queued</span>
        <span className="text-[11px] text-[#999]">·</span>
        <span className="text-[11px] text-[#f0ad4e]">{ing?.processing ?? 0} running</span>
        <span className="text-[11px] text-[#999]">·</span>
        <span className="text-[11px] text-[#5cb85c]">{ing?.failed ?? 0} failed</span>
      </div>
    </div>
  )

  if (showOnboarding) {
    return (
      <div className="flex flex-col gap-[12px] overflow-auto px-[24px] pb-[16px] pt-[20px]">
        <div>
          <p className="text-[22px] text-[#1b2431]">{project.name}</p>
          <p className="mt-1 text-[12px] text-[#7b8794]">
            {project.description ||
              'Project created just now. Start by adding sources, creating a brief, or searching the empty cabinet.'}
          </p>
        </div>

        <div className="rounded-[4px] border border-[#d6e0e8] bg-white px-[28px] py-[14px]">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
            NEW PROJECT
          </div>
          <div className="mt-1 flex items-start justify-between gap-6">
            <div className="min-w-0 flex-1">
              <h2 className="text-[13px] font-semibold text-[#1b2431]">Get Started</h2>
              <p className="mt-2 max-w-[620px] text-[12px] leading-6 text-[#7b8794]">
                The first dashboard state should build useful context quickly.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-[4px] bg-[#22a5f1] px-[16px] py-[10px] text-[12px] font-semibold text-white transition hover:bg-[#1a94db]"
                  onClick={() => setUploadModalOpen(true)}
                >
                  Upload Document
                </button>
                <button
                  type="button"
                  className="rounded-[4px] border border-[#d6e0e8] bg-white px-[16px] py-[10px] text-[12px] font-semibold text-[#1b2431] transition hover:border-[#22a5f1] hover:text-[#22a5f1]"
                  onClick={() => openTemplateDialog('adr')}
                >
                  Create Document
                </button>
                <Link
                  to="/search"
                  search={{ project: projectSlug, scope: 'current' }}
                  className="rounded-[4px] border border-[#d6e0e8] bg-white px-[16px] py-[10px] text-[12px] font-semibold text-[#1b2431] transition hover:border-[#22a5f1] hover:text-[#22a5f1]"
                >
                  Open Search
                </Link>
              </div>
            </div>
            <div className="min-w-[240px] text-[11px] text-[#333]">
              <div className="font-medium text-[#666]">Recommended first inputs</div>
              <ul className="mt-2 space-y-1.5 leading-5">
                <li>• project brief or scope note</li>
                <li>• vendor questionnaire or source PDF</li>
                <li>• initial requirements / risks list</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <section className={`${CARD} flex flex-col gap-[10px]`}>
            <span className={SECTION_LABEL}>ONBOARDING</span>
            <span className="text-[13px] font-semibold text-[#1b2431]">Suggested First Docs</span>
            <div className="space-y-3 text-[12px] text-[#333]">
              <div>
                <div className="font-semibold">1. Requirements brief</div>
                <div className="mt-1 text-[11px] text-[#7b8794]">
                  Capture purpose, stakeholders, and evaluation rules.
                </div>
              </div>
              <div>
                <div className="font-semibold">2. Session note</div>
                <div className="mt-1 text-[11px] text-[#7b8794]">
                  Record kickoff context and key follow-up actions.
                </div>
              </div>
              <div>
                <div className="font-semibold">3. Decision record</div>
                <div className="mt-1 text-[11px] text-[#7b8794]">
                  Start tracking why risky vendors are accepted or rejected.
                </div>
              </div>
            </div>
          </section>

          <section className={`${CARD} flex flex-col gap-[10px]`}>
            <span className={SECTION_LABEL}>EMPTY BUT READY</span>
            <span className="text-[13px] font-semibold text-[#1b2431]">Current Project State</span>
            <div className="space-y-1 text-[18px] font-semibold leading-7 text-[#1b2431]">
              <div>{docs.length} documents</div>
              <div>{entityCount} entities</div>
              <div>{pendingCount} review candidates</div>
            </div>
            <p className="text-[11px] leading-5 text-[#7b8794]">
              As soon as content is added, search, inbox, and sessions become project-specific.
            </p>
          </section>
        </div>

        <section className={`${CARD} flex flex-col gap-[10px]`}>
          <span className={SECTION_LABEL}>WORKFLOW NOTE</span>
          <span className="text-[13px] font-semibold text-[#1b2431]">Why This Landing Exists</span>
          <div className="space-y-3 text-[12px] leading-6 text-[#666]">
            <p>Create Project should not dead-end in a blank shell.</p>
            <p>
              The first dashboard state explains the next three actions and keeps the project switcher available at all times.
            </p>
            <p>
              If the user switches away immediately, the same header switcher should return them here until real project activity exists.
            </p>
          </div>
        </section>

        <UploadModal
          projectSlug={projectSlug}
          open={uploadModalOpen}
          onOpenChange={setUploadModalOpen}
          onSuccess={() => {
            void Promise.all([wq.refetch(), intQ.refetch(), sessQ.refetch()])
          }}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[12px] overflow-auto px-[24px] pb-[16px] pt-[20px]">
      {/* Title — Figma: 22px regular #1b2431 */}
      <p className="text-[22px] text-[#1b2431]">Dashboard</p>

      {/* ── System Health ── */}
      {systemHealthCard}

      {/* ── Row 2: Knowledge Summary + Attention Alerts ── */}
      <div className="flex gap-[12px]">
        {/* Knowledge Summary */}
        <div className={`${CARD} flex flex-1 flex-col gap-[10px]`}>
          <span className={CARD_TITLE}>Knowledge Summary</span>
          <div className={DIVIDER} />
          <div className="flex gap-[28px]">
            <div className="flex flex-col items-center gap-[2px]">
              <span className="text-[24px] font-bold text-[#1b2431]">1</span>
              <span className={SECTION_LABEL}>PROJECTS</span>
            </div>
            <div className="flex flex-col items-center gap-[2px]">
              <span className="text-[24px] font-bold text-[#1b2431]">{docs.length}</span>
              <span className={SECTION_LABEL}>DOCUMENTS</span>
            </div>
            <div className="flex flex-col items-center gap-[2px]">
              <span className="text-[24px] font-bold text-[#1b2431]">{entityCount}</span>
              <span className={SECTION_LABEL}>ENTITIES</span>
            </div>
          </div>
        </div>

        {/* Attention Alerts */}
        <div className={`${CARD} flex flex-1 flex-col gap-[10px]`}>
          <span className={CARD_TITLE}>Attention Alerts</span>
          <div className={DIVIDER} />
          {pendingCount > 0 ? (
            <>
              <div className="flex w-full flex-col items-center gap-[2px]">
                <Link
                  to="/projects/$slug/inbox"
                  params={{ slug: projectSlug }}
                  className="text-[28px] font-bold text-[#d9534f] hover:underline"
                >
                  {pendingCount}
                </Link>
                <span className={SECTION_LABEL}>CANDIDATES FOR REVIEW</span>
              </div>
              <div className={DIVIDER} />
            </>
          ) : null}
          {staleDocs.length > 0 && (
            <div className="flex items-center gap-[8px]">
              <span className={DOT_AMBER} />
              <span className="text-[11px] text-[#333]">{staleDocs.length} Stale Documents</span>
            </div>
          )}
          {openQuestions.length > 0 && (
            <div className="flex items-center gap-[8px]">
              <span className={DOT_BLUE} />
              <span className="text-[11px] text-[#333]">{openQuestions.length} Open Questions</span>
            </div>
          )}
          {pendingCount === 0 && staleDocs.length === 0 && openQuestions.length === 0 && (
            <span className="text-[11px] text-[#999]">No candidates pending</span>
          )}
        </div>
      </div>

      {/* ── Row 3: Agent Activity + Recent Activity ── */}
      <div className="flex flex-1 gap-[12px]">
        {/* Agent Activity */}
        <div className={`${CARD} flex flex-1 flex-col gap-[8px]`}>
          <div className="flex items-center justify-between">
            <span className={CARD_TITLE}>Agent Activity (24h)</span>
            <span className="rounded-[3px] bg-[#22a5f1] px-[8px] py-[3px] text-[10px] font-semibold text-white">
              {sessions.length} Sessions
            </span>
          </div>
          {/* Session status dots */}
          <div className="flex items-center gap-[12px]">
            {finalizedCount > 0 && (
              <div className="flex items-center gap-[4px]">
                <span className={DOT_GREEN} />
                <span className="text-[10px] text-[#333]">{finalizedCount} finalized</span>
              </div>
            )}
            {dirtyCount > 0 && (
              <div className="flex items-center gap-[4px]">
                <span className={DOT_AMBER} />
                <span className="text-[10px] text-[#333]">{dirtyCount} dirty</span>
              </div>
            )}
            {activeCount > 0 && (
              <div className="flex items-center gap-[4px]">
                <span className={DOT_BLUE} />
                <span className="text-[10px] text-[#333]">{activeCount} active</span>
              </div>
            )}
          </div>
          <div className={DIVIDER} />

          {/* Hook Events */}
          <span className={SECTION_LABEL}>HOOK EVENTS</span>
          {hookOrder.map((h) =>
            hookEvents[h] != null ? (
              <div key={h} className="flex items-start justify-between text-[10px]">
                <span className="text-[#333]">{h}</span>
                <span className="font-medium text-[#22a5f1]">{hookEvents[h]}</span>
              </div>
            ) : null,
          )}
          {Object.entries(hookEvents)
            .filter(([k]) => !hookOrder.includes(k))
            .map(([k, v]) => (
              <div key={k} className="flex items-start justify-between text-[10px]">
                <span className="text-[#333]">{k}</span>
                <span className="font-medium text-[#22a5f1]">{v}</span>
              </div>
            ))}
          {Object.keys(hookEvents).length === 0 && (
            <span className="text-[10px] text-[#999]">No hook events</span>
          )}

          <div className={DIVIDER} />

          {/* MCP Tool Calls */}
          <span className={SECTION_LABEL}>MCP TOOL CALLS</span>
          {Object.entries(mcpOps)
            .sort(([, a], [, b]) => b - a)
            .map(([k, v]) => (
              <div key={k} className="flex items-start justify-between text-[10px]">
                <span className="text-[#333]">{k}</span>
                <span className="font-medium text-[#22a5f1]">{v}</span>
              </div>
            ))}
          {Object.keys(mcpOps).length === 0 && (
            <span className="text-[10px] text-[#999]">No MCP tool calls</span>
          )}

          <div className={DIVIDER} />
          <Link
            to="/projects/$slug/sessions"
            params={{ slug: projectSlug }}
            className="text-[11px] font-medium text-[#22a5f1]"
          >
            View All Sessions →
          </Link>
        </div>

        {/* Recent Activity */}
        <div className={`${CARD} flex flex-1 flex-col gap-[8px]`}>
          <span className={CARD_TITLE}>Recent Activity</span>
          <div className={DIVIDER} />
          {activity.length === 0 ? (
            <span className="text-[11px] text-[#999]">No recent activity.</span>
          ) : (
            activity.map((e) => (
              <div key={e.id} className="flex items-start gap-[10px]">
                <span className="text-[11px] text-[#666]">{opIcon(e.operation)}</span>
                <div className="flex flex-col gap-px">
                  <span className={`text-[11px] font-medium ${opColor(e.operation)}`}>
                    {opLabel(e)}
                  </span>
                  <span className="text-[10px] text-[#999]">
                    {e.actor_type} · {formatTime(e.created_at)}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
