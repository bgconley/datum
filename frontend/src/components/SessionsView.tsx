import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Info } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useContextPanel } from '@/lib/context-panel'
import { api, type SessionSummary, type SessionDetail } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(startIso: string, endIso: string | null): string {
  const start = new Date(startIso).getTime()
  const end = endIso ? new Date(endIso).getTime() : Date.now()
  const ms = end - start
  const totalMinutes = Math.floor(ms / 60_000)
  if (totalMinutes < 60) return `${totalMinutes}m`
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

function statusDotColor(status: string, isDirty: boolean): string {
  if (status === 'active' && isDirty) return 'bg-amber-500'
  if (status === 'active') return 'bg-green-500'
  if (status === 'finalized') return 'bg-green-500'
  if (status === 'abandoned') return 'bg-red-500'
  return 'bg-muted-foreground'
}

function statusTextColor(status: string): string {
  if (status === 'finalized') return 'text-green-600'
  if (status === 'abandoned') return 'text-red-500'
  return 'text-muted-foreground'
}

// ---------------------------------------------------------------------------
// Context panel content
// ---------------------------------------------------------------------------

function SessionContextPanel({ detail }: { detail: SessionDetail }) {
  const hookEvents = detail.hook_events
  const deltas = detail.deltas
  const auditEvents = detail.audit_events

  // Compute delta summary
  const filesTouched = new Set<string>()
  let linesAdded = 0
  let linesRemoved = 0
  for (const delta of deltas) {
    const d = delta.detail
    if (typeof d['path'] === 'string') filesTouched.add(d['path'] as string)
    if (typeof d['file'] === 'string') filesTouched.add(d['file'] as string)
    if (typeof d['additions'] === 'number') linesAdded += d['additions'] as number
    if (typeof d['deletions'] === 'number') linesRemoved += d['deletions'] as number
  }

  return (
    <ScrollArea className="h-full">
      <div className="space-y-5 p-5">
        {/* Header */}
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Context: Session
          </div>
        </div>

        {/* Session metadata */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Session ID</span>
            <span className="font-mono text-xs">{detail.session_id}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Agent</span>
            <span className="text-primary">{detail.client_type}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Enforcement</span>
            <Badge variant="outline">{detail.enforcement_mode}</Badge>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Preflight</span>
            <span className="font-medium text-green-600">
              {hookEvents.some(
                (event) =>
                  event.hook_type === 'SessionStart' &&
                  (event.detail['status'] === 'ok' || event.detail['preflight'] === 'ok'),
              )
                ? 'PASS'
                : hookEvents.length > 0
                  ? 'FAIL'
                  : '--'}
            </span>
          </div>
        </div>

        <Separator />

        {/* Hook event timeline */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Hook event timeline
          </div>
          {hookEvents.length === 0 ? (
            <div className="flex items-center gap-2 rounded border border-border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">
              <Info className="size-4 shrink-0 text-muted-foreground/60" />
              No hook telemetry for this session
            </div>
          ) : (
            <div className="space-y-1">
              {hookEvents.map((event) => (
                <div key={event.id} className="flex gap-2 text-xs">
                  <span className="shrink-0 font-mono text-muted-foreground">
                    {formatTime(event.created_at)}
                  </span>
                  <span>
                    <span className="font-medium">{event.hook_type}</span>{' '}
                    <span className="text-muted-foreground">
                      {event.detail['status']
                        ? String(event.detail['status'])
                        : event.detail['preflight']
                          ? `preflight ${String(event.detail['preflight'])}`
                          : ''}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* MCP tool call log */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            MCP tool call log
          </div>
          {auditEvents.length === 0 ? (
            <div className="text-xs text-muted-foreground">No tool calls recorded.</div>
          ) : (
            <div className="space-y-1">
              {auditEvents.map((event) => (
                <div key={event.id} className="flex gap-2 text-xs">
                  <span className="shrink-0 font-mono text-muted-foreground">
                    {formatTime(event.created_at)}
                  </span>
                  <span>
                    <span className="font-medium">{event.operation}</span>
                    {event.metadata['result_count'] != null && (
                      <span className="text-muted-foreground">
                        {' '}
                        {String(event.metadata['result_count'])} results
                      </span>
                    )}
                    {event.target_path && (
                      <span className="text-muted-foreground"> {event.target_path}</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* Delta summary */}
        <div className="space-y-3">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Delta summary
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Files touched</span>
              <span className="font-medium">{filesTouched.size || deltas.length}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Lines added</span>
              <span className="font-medium text-green-600">+{linesAdded}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Lines removed</span>
              <span className="font-medium text-red-500">-{linesRemoved}</span>
            </div>
          </div>
        </div>

        <Separator />

        {/* Finalize button */}
        {detail.status === 'active' && (
          <Button className="w-full">Finalize session</Button>
        )}
      </div>
    </ScrollArea>
  )
}

// ---------------------------------------------------------------------------
// Active session card
// ---------------------------------------------------------------------------

function ActiveSessionCard({
  session,
  selected,
  onSelect,
}: {
  session: SessionSummary
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full cursor-pointer rounded border bg-white px-4 py-3 text-left transition-colors hover:bg-accent/30 ${
        selected ? 'border-l-2 border-l-primary border-t-border border-r-border border-b-border' : 'border-border'
      }`}
    >
      {/* Row 1: status dot, agent, badge, session id */}
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${statusDotColor(session.status, session.is_dirty)}`} />
        <span className="font-medium">{session.client_type}</span>
        {session.is_dirty && (
          <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-700">
            dirty
          </Badge>
        )}
        {session.status === 'active' && !session.is_dirty && (
          <Badge variant="default">active</Badge>
        )}
        <span className="ml-auto font-mono text-xs text-muted-foreground">{session.session_id}</span>
      </div>

      {/* Row 2: metadata line */}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>Started: {formatRelativeTime(session.started_at)}</span>
        <span>Deltas: {session.delta_count}</span>
      </div>

      {/* Row 3: action buttons */}
      <div className="mt-3 flex gap-2" onClick={(event) => event.stopPropagation()}>
        {session.is_dirty && (
          <Button size="xs" variant="default">
            Flush
          </Button>
        )}
        <Button size="xs" variant="outline">
          View note
        </Button>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface SessionsViewProps {
  projectSlug: string
}

const EMPTY_SESSIONS: SessionSummary[] = []

export function SessionsView({ projectSlug }: SessionsViewProps) {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const { setContent } = useContextPanel()

  // Fetch sessions list with polling
  const sessionsQuery = useQuery({
    queryKey: queryKeys.dashboardSessions(projectSlug),
    queryFn: () => api.dashboard.sessions(projectSlug),
    refetchInterval: 30_000,
  })

  const sessions = sessionsQuery.data ?? EMPTY_SESSIONS

  // Split into active and recent
  const activeSessions = sessions.filter((session) => session.status === 'active')
  const recentSessions = sessions.filter((session) => session.status !== 'active')

  // Auto-select first active session when none selected
  useEffect(() => {
    if (!selectedSessionId && activeSessions.length > 0) {
      setSelectedSessionId(activeSessions[0].session_id)
    }
  }, [activeSessions, selectedSessionId])

  // Fetch session detail when selected, with faster polling
  const detailQuery = useQuery({
    queryKey: queryKeys.sessionDetail(projectSlug, selectedSessionId ?? ''),
    queryFn: () => api.dashboard.sessionDetail(projectSlug, selectedSessionId!),
    enabled: Boolean(selectedSessionId),
    refetchInterval: 5_000,
  })

  // Push context panel content when detail changes
  useEffect(() => {
    if (detailQuery.data) {
      setContent(<SessionContextPanel detail={detailQuery.data} />)
    } else if (!selectedSessionId) {
      setContent(null)
    }
    return () => setContent(null)
  }, [detailQuery.data, selectedSessionId, setContent])

  // Loading state
  if (sessionsQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading sessions...</div>
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Sessions</h1>
        <span className="font-mono text-sm text-primary">{projectSlug}</span>
      </div>

      {/* Active sessions section */}
      <div>
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Active sessions
          </h2>
          {activeSessions.length > 0 && (
            <Badge variant="default">{activeSessions.length} active</Badge>
          )}
        </div>

        <div className="mt-4 space-y-3">
          {activeSessions.length === 0 ? (
            <div className="rounded border border-border bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground">
              No active sessions
            </div>
          ) : (
            activeSessions.map((session) => (
              <ActiveSessionCard
                key={session.id}
                session={session}
                selected={selectedSessionId === session.session_id}
                onSelect={() => setSelectedSessionId(session.session_id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Recent sessions table */}
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Recent sessions
        </h2>

        <div className="mt-4 overflow-hidden rounded border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Date
                </th>
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Agent
                </th>
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Deltas
                </th>
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Duration
                </th>
                <th className="w-10 px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {recentSessions.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-6 text-center text-sm text-muted-foreground"
                  >
                    No recent sessions
                  </td>
                </tr>
              ) : (
                recentSessions.map((session) => (
                  <tr
                    key={session.id}
                    className="cursor-pointer border-b border-border last:border-b-0 transition-colors hover:bg-accent/30"
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {formatDate(session.started_at)}
                    </td>
                    <td className="px-4 py-2.5 text-primary">{session.client_type}</td>
                    <td className="px-4 py-2.5">
                      <span className={`font-medium ${statusTextColor(session.status)}`}>
                        {session.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">{session.delta_count}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {formatDuration(session.started_at, session.ended_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <ArrowRight className="size-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
