import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { useContextPanel } from '@/lib/context-panel'
import { api, type SessionSummary, type SessionDetail } from '@/lib/api'
import { notify } from '@/lib/notifications'
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
  return new Date(iso).toISOString().slice(0, 10)
}

function formatDuration(startIso: string, endIso: string | null): string {
  const start = new Date(startIso).getTime()
  const end = endIso ? new Date(endIso).getTime() : Date.now()
  const ms = end - start
  const totalMinutes = Math.floor(ms / 60_000)
  if (totalMinutes < 60) return `${totalMinutes} min`
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return minutes > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${hours}h`
}

function statusDot(status: string, isDirty: boolean): string {
  if (status === 'active' && isDirty) return 'bg-[#f0ad4e]'
  if (status === 'active') return 'bg-[#22a5f1]'
  if (status === 'finalized') return 'bg-[#5cb85c]'
  if (status === 'abandoned') return 'bg-[#d9534f]'
  return 'bg-[#999]'
}

function statusColor(status: string): string {
  if (status === 'finalized') return 'text-[#5cb85c]'
  if (status === 'abandoned') return 'text-[#d9534f]'
  return 'text-[#666]'
}

// ---------------------------------------------------------------------------
// Context panel
// ---------------------------------------------------------------------------

function SessionContextPanel({
  detail,
  isFinalizing,
  onFinalize,
}: {
  detail: SessionDetail
  isFinalizing: boolean
  onFinalize: () => void
}) {
  const hookEvents = detail.hook_events
  const auditEvents = detail.audit_events
  const deltas = detail.deltas

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

  const preflightOk = hookEvents.some(
    (event) =>
      event.hook_type === 'SessionStart' &&
      (event.detail['status'] === 'ok' || event.detail['preflight'] === 'ok'),
  )

  return (
    <div className="flex flex-col gap-[8px] p-[16px]">
      <span className="text-[11px] font-semibold text-[#666]">CONTEXT: SESSION</span>
      <div className="h-px w-full bg-[#e1e8ed]" />

      <div className="flex items-start justify-between text-[10px]">
        <span className="text-[#666]">Session ID</span>
        <span className="font-mono text-[#333]">{detail.session_id}</span>
      </div>
      <div className="flex items-start justify-between text-[10px]">
        <span className="text-[#666]">Agent</span>
        <span className="font-mono text-[#333]">{detail.client_type}</span>
      </div>
      <div className="flex items-start justify-between">
        <span className="text-[10px] text-[#666]">Enforcement</span>
        <span className="rounded-[3px] bg-[#d9edf7] px-[8px] py-[3px] text-[10px] font-semibold text-[#22a5f1]">
          {detail.enforcement_mode}
        </span>
      </div>
      <div className="flex items-start justify-between">
        <span className="text-[10px] text-[#666]">Preflight</span>
        <div className="flex items-center gap-[4px]">
          <div
            className={`size-[8px] rounded-full ${preflightOk ? 'bg-[#5cb85c]' : hookEvents.length > 0 ? 'bg-[#d9534f]' : 'bg-[#999]'}`}
          />
          <span
            className={`text-[10px] font-medium ${preflightOk ? 'text-[#5cb85c]' : hookEvents.length > 0 ? 'text-[#d9534f]' : 'text-[#999]'}`}
          >
            {preflightOk ? 'PASS' : hookEvents.length > 0 ? 'FAIL' : '--'}
          </span>
        </div>
      </div>
      <div className="h-px w-full bg-[#e1e8ed]" />

      <span className="text-[11px] font-semibold text-[#666]">HOOK EVENT TIMELINE</span>
      {hookEvents.length === 0 ? (
        <span className="text-[9px] text-[#999]">No hook telemetry</span>
      ) : (
        hookEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-[8px]">
            <span className="shrink-0 font-mono text-[9px] text-[#999]">
              {formatTime(event.created_at)}
            </span>
            <span className="text-[10px] font-medium text-[#333]">{event.hook_type}</span>
            <span className="truncate text-[9px] text-[#666]">
              {event.detail['status']
                ? String(event.detail['status'])
                : event.detail['preflight']
                  ? `preflight ${String(event.detail['preflight'])}`
                  : ''}
            </span>
          </div>
        ))
      )}
      <div className="h-px w-full bg-[#e1e8ed]" />

      <span className="text-[11px] font-semibold text-[#666]">MCP TOOL CALL LOG</span>
      {auditEvents.length === 0 ? (
        <span className="text-[9px] text-[#999]">No tool calls</span>
      ) : (
        auditEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-[8px]">
            <span className="shrink-0 font-mono text-[9px] text-[#999]">
              {formatTime(event.created_at)}
            </span>
            <span className="text-[10px] font-medium text-[#22a5f1]">{event.operation}</span>
            <span className="truncate text-[9px] text-[#666]">
              {event.metadata['result_count'] != null
                ? `${String(event.metadata['result_count'])} results`
                : event.target_path ?? ''}
            </span>
          </div>
        ))
      )}
      <div className="h-px w-full bg-[#e1e8ed]" />

      <span className="text-[11px] font-semibold text-[#666]">DELTA SUMMARY</span>
      <div className="flex items-start justify-between text-[10px]">
        <span className="text-[#666]">Files touched</span>
        <span className="font-semibold text-[#333]">{filesTouched.size || deltas.length}</span>
      </div>
      <div className="flex items-start justify-between text-[10px]">
        <span className="text-[#666]">Lines added</span>
        <span className="font-semibold text-[#5cb85c]">+{linesAdded}</span>
      </div>
      <div className="flex items-start justify-between text-[10px]">
        <span className="text-[#666]">Lines removed</span>
        <span className="font-semibold text-[#d9534f]">-{linesRemoved}</span>
      </div>

      {detail.status === 'active' && (
        <button
          type="button"
          onClick={onFinalize}
          disabled={isFinalizing}
          className="rounded-[4px] bg-[#5cb85c] px-[12px] py-[8px] text-[10px] font-semibold text-white"
        >
          {isFinalizing ? 'FINALIZING...' : 'FINALIZE SESSION'}
        </button>
      )}
    </div>
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
  const [finalizingSessionId, setFinalizingSessionId] = useState<string | null>(null)
  const { setContent } = useContextPanel()
  const queryClient = useQueryClient()

  const sessionsQuery = useQuery({
    queryKey: queryKeys.dashboardSessions(projectSlug),
    queryFn: () => api.dashboard.sessions(projectSlug),
    refetchInterval: 30_000,
  })

  const sessions = sessionsQuery.data ?? EMPTY_SESSIONS
  const activeSessions = sessions.filter((s) => s.status === 'active')
  const recentSessions = sessions.filter((s) => s.status !== 'active')

  useEffect(() => {
    if (!selectedSessionId && activeSessions.length > 0) {
      setSelectedSessionId(activeSessions[0].session_id)
    }
  }, [activeSessions, selectedSessionId])

  const detailQuery = useQuery({
    queryKey: queryKeys.sessionDetail(projectSlug, selectedSessionId ?? ''),
    queryFn: () => api.dashboard.sessionDetail(projectSlug, selectedSessionId!),
    enabled: Boolean(selectedSessionId),
    refetchInterval: 5_000,
  })

  const invalidateSessions = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardSessions(projectSlug) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardActivity(projectSlug) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.agentActivity(projectSlug) }),
      selectedSessionId
        ? queryClient.invalidateQueries({
            queryKey: queryKeys.sessionDetail(projectSlug, selectedSessionId),
          })
        : Promise.resolve(),
    ])
  }

  const handleFinalize = async (detail: SessionDetail) => {
    setFinalizingSessionId(detail.session_id)
    try {
      if (detail.is_dirty) {
        await api.lifecycle.flush(detail.session_id)
      }
      await api.lifecycle.finalize(detail.session_id)
      await invalidateSessions()
    } catch (error) {
      notify(String(error))
    } finally {
      setFinalizingSessionId(null)
    }
  }

  useEffect(() => {
    if (detailQuery.data) {
      setContent(
        <SessionContextPanel
          detail={detailQuery.data}
          isFinalizing={finalizingSessionId === detailQuery.data.session_id}
          onFinalize={() => {
            void handleFinalize(detailQuery.data)
          }}
        />,
      )
    } else if (!selectedSessionId) {
      setContent(null)
    }
    return () => setContent(null)
  }, [detailQuery.data, finalizingSessionId, selectedSessionId, setContent])

  if (sessionsQuery.isLoading) {
    return (
      <div className="px-[24px] py-[20px] text-[11px] text-[#666]">Loading sessions&hellip;</div>
    )
  }

  return (
    <div className="flex flex-col gap-[14px] px-[24px] pb-[16px] pt-[20px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] text-[#1b2431]">Sessions</h1>
        <span className="text-[13px] text-[#22a5f1]">{projectSlug}</span>
      </div>

      {/* Active Sessions card */}
      <div className="flex flex-col gap-[12px] rounded-[4px] border border-[#e1e8ed] bg-white px-[20px] py-[16px]">
        <div className="flex items-center gap-[8px]">
          <span className="text-[13px] font-semibold text-[#333]">Active Sessions</span>
          {activeSessions.length > 0 && (
            <span className="rounded-[3px] bg-[#22a5f1] px-[8px] py-[3px] text-[10px] font-semibold text-white">
              {activeSessions.length} active
            </span>
          )}
        </div>
        <div className="h-px w-full bg-[#e1e8ed]" />

        {activeSessions.length === 0 ? (
          <div className="py-[10px] text-[11px] text-[#666]">No active sessions</div>
        ) : (
          activeSessions.map((session) => {
            const isSelected = selectedSessionId === session.session_id
            const isDirty = session.is_dirty
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => setSelectedSessionId(session.session_id)}
                className={`flex h-[100px] w-full items-start overflow-hidden rounded-[4px] text-left ${
                  isDirty
                    ? 'border border-[#22a5f1] border-l-[3px] bg-[rgba(34,165,241,0.04)]'
                    : isSelected
                      ? 'border border-[#22a5f1] bg-white'
                      : 'border border-[#e1e8ed] bg-white'
                }`}
              >
                <div className="flex min-w-0 flex-1 flex-col gap-[6px] px-[16px] py-[12px]">
                  {/* Row 1: dot + name + badge + session ID */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-[8px]">
                      <div
                        className={`size-[8px] shrink-0 rounded-full ${statusDot(session.status, isDirty)}`}
                      />
                      <span className="text-[13px] font-semibold text-[#333]">
                        {session.client_type}
                      </span>
                      {isDirty && (
                        <span className="rounded-[3px] bg-[#fcf8e3] px-[8px] py-[3px] text-[10px] font-semibold text-[#f0ad4e]">
                          dirty
                        </span>
                      )}
                      {!isDirty && session.status === 'active' && (
                        <span className="rounded-[3px] bg-[#d9edf7] px-[8px] py-[3px] text-[10px] font-semibold text-[#22a5f1]">
                          active
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-[10px] text-[#999]">
                      {session.session_id}
                    </span>
                  </div>
                  {/* Row 2: stats */}
                  <div className="flex items-center gap-[16px] text-[10px] text-[#666]">
                    <span>Started: {formatRelativeTime(session.started_at)}</span>
                    <span>Deltas: {session.delta_count}</span>
                    {isDirty && (
                      <span className="font-medium text-[#f0ad4e]">
                        Pending: {session.delta_count}
                      </span>
                    )}
                  </div>
                  {/* Row 3: actions */}
                  <div
                    className="flex items-start gap-[8px]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {isDirty && (
                      <div className="rounded-[4px] bg-[#22a5f1] px-[10px] py-[5px] text-[9px] font-semibold text-white">
                        FLUSH
                      </div>
                    )}
                    <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[10px] py-[5px] text-[9px] font-semibold text-[#333]">
                      VIEW NOTE
                    </div>
                  </div>
                </div>
              </button>
            )
          })
        )}
      </div>

      {/* Recent Sessions table */}
      <div className="flex flex-1 flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white">
        {/* Header row */}
        <div className="flex items-center justify-between border-b border-[#e1e8ed] bg-[#f3f6f8] px-[20px] py-[12px]">
          <div className="flex h-[16px] items-center">
            <span className="text-[9px] font-semibold text-[#666]">DATE</span>
          </div>
          <div className="flex h-[16px] items-center">
            <span className="text-[9px] font-semibold text-[#666]">AGENT</span>
          </div>
          <div className="flex h-[16px] items-center">
            <span className="text-[9px] font-semibold text-[#666]">STATUS</span>
          </div>
          <div className="flex h-[16px] items-center">
            <span className="text-[9px] font-semibold text-[#666]">FILES</span>
          </div>
          <div className="flex h-[16px] items-center">
            <span className="text-[9px] font-semibold text-[#666]">DURATION</span>
          </div>
          <div className="h-[16px] w-[60px]" />
        </div>

        {recentSessions.length === 0 ? (
          <div className="px-[20px] py-[16px] text-[11px] text-[#666]">No recent sessions</div>
        ) : (
          recentSessions.map((session) => (
            <button
              key={session.id}
              type="button"
              onClick={() => setSelectedSessionId(session.session_id)}
              className="flex w-full items-center justify-between border-b border-[rgba(225,232,237,0.5)] px-[20px] py-[10px] text-left last:border-b-0 hover:bg-[#f9fafb]"
            >
              <div className="flex h-[16px] items-center">
                <span className="text-[11px] text-[#333]">{formatDate(session.started_at)}</span>
              </div>
              <div className="flex h-[16px] items-center">
                <span className="text-[11px] font-medium text-[#22a5f1]">
                  {session.client_type}
                </span>
              </div>
              <div className="flex h-[16px] items-center">
                <span className={`text-[11px] font-medium ${statusColor(session.status)}`}>
                  {session.status}
                </span>
              </div>
              <div className="flex h-[16px] items-center">
                <span className="text-[11px] text-[#333]">{session.delta_count}</span>
              </div>
              <div className="flex h-[16px] items-center">
                <span className="text-[11px] text-[#666]">
                  {formatDuration(session.started_at, session.ended_at)}
                </span>
              </div>
              <div className="flex h-[16px] w-[60px] items-center">
                <span className="text-[11px] font-medium text-[#22a5f1]">{'\u2192'}</span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
