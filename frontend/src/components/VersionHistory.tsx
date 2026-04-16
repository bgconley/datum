import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, GitCompareArrows, RotateCcw } from 'lucide-react'
import { Diff, Hunk, parseDiff } from 'react-diff-view'
import 'react-diff-view/style/index.css'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { api, type VersionDiff, type VersionInfo } from '@/lib/api'
import { useContextPanel } from '@/lib/context-panel'
import { notify } from '@/lib/notifications'
import { queryKeys } from '@/lib/query-keys'

const EMPTY_VERSIONS: VersionInfo[] = []

function HistoryContextPanel({
  versions,
  selectedA,
  selectedB,
  diff,
}: {
  versions: VersionInfo[]
  selectedA: number | null
  selectedB: number | null
  diff: VersionDiff | null
}) {
  const latestVersion = versions.length > 0 ? versions[versions.length - 1] : null

  return (
    <div className="flex flex-col gap-[10px] p-[16px]">
      <p className="text-[11px] font-semibold text-[#666]">CONTEXT: HISTORY</p>
      <div className="h-px w-full bg-[#e1e8ed]" />

      {latestVersion && (
        <>
          <div className="flex items-start justify-between text-[11px]">
            <span className="text-[#666]">Change Source</span>
            <span className="font-medium text-[#333]">
              {latestVersion.created_by ?? latestVersion.change_source ?? 'unknown'}
            </span>
          </div>
          <div className="flex items-start justify-between text-[11px]">
            <span className="text-[#666]">Diffing</span>
            <span className="font-medium text-[#333]">
              {selectedA && selectedB
                ? `v${selectedA.toString().padStart(3, '0')} ↔ v${selectedB.toString().padStart(3, '0')}`
                : 'N/A'}
            </span>
          </div>
          <div className="h-px w-full bg-[#e1e8ed]" />

          <p className="text-[11px] font-semibold text-[#666]">TECHNICAL METADATA</p>
          <div className="space-y-1 font-mono text-[11px] text-[#333]">
            <div className="flex justify-between">
              <span className="text-[#666]">File</span>
              <span>{latestVersion.version_file}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#666]">Hash</span>
              <span className="truncate max-w-[120px]">{latestVersion.content_hash}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#666]">Size</span>
              <span>-</span>
            </div>
          </div>
          <div className="h-px w-full bg-[#e1e8ed]" />

          <p className="text-[11px] font-semibold text-[#666]">PIPELINE STATUS</p>
          <div className="space-y-2 text-[11px]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-[6px]">
                <span className="inline-block size-[8px] rounded-full bg-[#5cb85c]" />
                <span className="text-[#666]">Chunking</span>
              </div>
              <span className="font-medium text-[#333]">OK</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-[6px]">
                <span className="inline-block size-[8px] rounded-full bg-[#5cb85c]" />
                <span className="text-[#666]">Embedding</span>
              </div>
              <span className="font-medium text-[#333]">OK</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-[6px]">
                <span className="inline-block size-[8px] rounded-full bg-[#5cb85c]" />
                <span className="text-[#666]">NER</span>
              </div>
              <span className="font-medium text-[#333]">OK</span>
            </div>
          </div>
          <div className="flex gap-[8px]">
            <button type="button" className="rounded-[4px] bg-[#22a5f1] px-[12px] py-[6px] text-[10px] font-semibold text-white">
              RE-INDEX
            </button>
            <button type="button" className="rounded-[4px] bg-[#5cb85c] px-[12px] py-[6px] text-[10px] font-semibold text-white">
              RE-EXTRACT
            </button>
          </div>
        </>
      )}
    </div>
  )
}

interface VersionHistoryProps {
  projectSlug: string
  docPath: string
}

export function VersionHistory({ projectSlug, docPath }: VersionHistoryProps) {
  const [selectedA, setSelectedA] = useState<number | null>(null)
  const [selectedB, setSelectedB] = useState<number | null>(null)
  const [viewType, setViewType] = useState<'split' | 'unified'>('split')
  const queryClient = useQueryClient()
  const { setContent } = useContextPanel()
  const navigate = useNavigate()

  const versionsQuery = useQuery({
    queryKey: queryKeys.versions(projectSlug, docPath),
    queryFn: () => api.versions.list(projectSlug, docPath),
  })
  const versions = versionsQuery.data ?? EMPTY_VERSIONS

  useEffect(() => {
    if (versions.length >= 2) {
      const nextSelectedA = versions.at(-2)?.version_number ?? null
      const nextSelectedB = versions.at(-1)?.version_number ?? null
      setSelectedA((current) => (current === nextSelectedA ? current : nextSelectedA))
      setSelectedB((current) => (current === nextSelectedB ? current : nextSelectedB))
    } else if (versions.length === 1) {
      setSelectedA((current) => (current === versions[0].version_number ? current : versions[0].version_number))
      setSelectedB((current) => (current === versions[0].version_number ? current : versions[0].version_number))
    }
  }, [versions])

  const diffQuery = useQuery({
    queryKey:
      selectedA != null && selectedB != null
        ? queryKeys.versionDiff(projectSlug, docPath, selectedA, selectedB)
        : ['versions', 'diff', 'idle'],
    queryFn: () => api.versions.diff(projectSlug, docPath, selectedA!, selectedB!),
    enabled: selectedA != null && selectedB != null && selectedA !== selectedB,
  })
  const diff = diffQuery.data ?? null

  useEffect(() => {
    setContent(
      <HistoryContextPanel
        versions={versions}
        selectedA={selectedA}
        selectedB={selectedB}
        diff={diff}
      />,
    )
    return () => setContent(null)
  }, [diff, selectedA, selectedB, setContent, versions])

  const parsedDiff = useMemo(
    () => (diff?.diff_text ? parseDiff(diff.diff_text) : []),
    [diff?.diff_text],
  )

  const restoreMutation = useMutation({
    mutationFn: async (versionNumber: number) =>
      api.versions.restore(projectSlug, docPath, versionNumber, {
        label: `Restore v${versionNumber.toString().padStart(3, '0')}`,
      }),
    onSuccess: async (restored) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.document(projectSlug, restored.relative_path) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.versions(projectSlug, restored.relative_path) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectSlug) }),
      ])
      navigate({
        to: '/projects/$slug/docs/$',
        params: { slug: projectSlug, _splat: restored.relative_path },
      })
    },
    onError: (error) => {
      notify(String(error))
    },
  })

  const handleRestore = async (versionNumber: number) => {
    await restoreMutation.mutateAsync(versionNumber)
  }

  if (versionsQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading version history…</div>
  }

  const filename = docPath.split('/').pop() ?? docPath

  return (
    <div className="flex flex-col gap-[12px] overflow-auto px-[24px] py-[20px]">
      {/* Title — Figma: filename (History) Diffing: vXXX ↔ vYYY */}
      <div className="flex items-center gap-[8px]">
        <span className="text-[18px] font-semibold text-[#1b2431]">{filename}</span>
        <Link
          to="/projects/$slug/docs/$"
          params={{ slug: projectSlug, _splat: docPath }}
          className="text-[13px] text-[#22a5f1] hover:underline"
        >
          (History)
        </Link>
        {selectedA != null && selectedB != null && (
          <span className="text-[13px] text-[#999]">
            Diffing: v{selectedA.toString().padStart(3, '0')} ↔ v{selectedB.toString().padStart(3, '0')}
          </span>
        )}
      </div>

      {/* Split: version list + diff */}
      <div className="flex gap-[12px]" style={{ minHeight: 0, flex: '1 1 0' }}>
        {/* Version list — left ~30% */}
        <div className="flex w-[280px] shrink-0 flex-col">
          {/* Table header */}
          <div className="flex border-b border-[#e1e8ed] pb-[6px] text-[9px] font-semibold text-[#666]">
            <span className="flex-1">VERSION</span>
            <span className="w-[80px] text-right">DATE</span>
          </div>

          {/* Version rows */}
          <div className="mt-[4px] space-y-0">
            {[...versions].reverse().map((version, i) => {
              const isLatest = i === 0
              const active = version.version_number === selectedB

              return (
                <button
                  key={version.version_number}
                  type="button"
                  onClick={() => {
                    setSelectedA(selectedB)
                    setSelectedB(version.version_number)
                  }}
                  className={`flex w-full items-start justify-between border-l-[3px] px-[12px] py-[8px] text-left ${
                    active
                      ? 'border-l-[#22a5f1] bg-[#e8f4fd]'
                      : 'border-l-transparent hover:bg-[#f7f9fa]'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-[6px]">
                      <span className={`text-[12px] ${active ? 'font-semibold text-[#22a5f1]' : 'text-[#333]'}`}>
                        v{version.version_number.toString().padStart(3, '0')}
                      </span>
                      {isLatest && (
                        <span className="text-[10px] text-[#5cb85c]">(Current)</span>
                      )}
                    </div>
                    <div className="mt-[2px] text-[10px] text-[#999]">
                      by {version.created_by ?? version.change_source ?? 'web-ui'}
                    </div>
                    {active && isLatest && (
                      <button
                        type="button"
                        className="mt-[6px] rounded-[3px] bg-[#22a5f1] px-[10px] py-[4px] text-[10px] font-semibold text-white"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleRestore(version.version_number)
                        }}
                        disabled={restoreMutation.isPending}
                      >
                        {restoreMutation.isPending ? 'Restoring…' : 'RESTORE'}
                      </button>
                    )}
                  </div>
                  <span className="text-[11px] text-[#333]">
                    {new Date(version.created_at).toLocaleDateString()}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Diff — right ~70% */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between pb-[8px]">
            <span className="text-[11px] font-semibold text-[#666]">
              UNIFIED DIFF{' '}
              {selectedA != null && selectedB != null
                ? `v${selectedA.toString().padStart(3, '0')} ↔ v${selectedB.toString().padStart(3, '0')}`
                : ''}
            </span>
            <div className="flex items-center gap-[4px]">
              <button
                type="button"
                className={`rounded-[4px] px-[10px] py-[4px] text-[10px] font-semibold ${
                  viewType === 'split' ? 'bg-[#22a5f1] text-white' : 'bg-white border border-[#e1e8ed] text-[#333]'
                }`}
                onClick={() => setViewType('split')}
              >
                Split
              </button>
              <button
                type="button"
                className={`rounded-[4px] px-[10px] py-[4px] text-[10px] font-semibold ${
                  viewType === 'unified' ? 'bg-[#22a5f1] text-white' : 'bg-white border border-[#e1e8ed] text-[#333]'
                }`}
                onClick={() => setViewType('unified')}
              >
                Unified
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto rounded-[4px] border border-[#e1e8ed] bg-white">
            {selectedA === selectedB ? (
              <div className="p-[24px] text-[12px] text-[#999]">
                Select two different versions to compare.
              </div>
            ) : parsedDiff.length === 0 ? (
              <div className="p-[24px] text-[12px] text-[#999]">
                No diff available for the selected versions.
              </div>
            ) : (
              <div className="datum-diff-view">
                {parsedDiff.map((file) => (
                  <Diff
                    key={`${file.oldRevision}-${file.newRevision}`}
                    viewType={viewType}
                    diffType={file.type}
                    hunks={file.hunks}
                  >
                    {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
                  </Diff>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
