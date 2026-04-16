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
    <div className="space-y-5 p-5">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Context: History
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">Version history</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Compare immutable cabinet versions and restore prior states without rewriting history.
        </p>
      </div>

      {latestVersion && (
        <div className="rounded border border-border bg-muted p-4">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Change source
          </div>
          <div className="mt-2 text-sm">
            {latestVersion.created_by ?? latestVersion.change_source ?? 'unknown'}
          </div>
        </div>
      )}

      {latestVersion && (
        <div className="rounded border border-border bg-muted p-4">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Technical metadata
          </div>
          <div className="mt-2 space-y-1 font-mono text-xs text-muted-foreground">
            <div>file: {latestVersion.version_file}</div>
            <div>hash: {latestVersion.content_hash}</div>
            <div>indexing: {latestVersion.indexing_status ?? 'unknown'}</div>
          </div>
        </div>
      )}

      <Separator />

      <div className="rounded border border-border bg-muted p-4">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Selected comparison
        </div>
        <div className="mt-3 space-y-2 text-sm">
          <div>Base: {selectedA ? `v${selectedA.toString().padStart(3, '0')}` : 'Not selected'}</div>
          <div>Target: {selectedB ? `v${selectedB.toString().padStart(3, '0')}` : 'Not selected'}</div>
          {diff && (
            <div className="flex items-center gap-3 text-xs">
              <Badge className="border-green-200 bg-green-50 text-green-700">+{diff.additions}</Badge>
              <Badge className="border-red-200 bg-red-50 text-red-700">-{diff.deletions}</Badge>
            </div>
          )}
        </div>
      </div>

      {latestVersion && (
        <div className="space-y-3">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Pipeline status
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="inline-block size-2 rounded-full bg-green-500" />
            {latestVersion.indexing_status ?? 'unknown'}
          </div>
          <div className="flex gap-2">
            <Button type="button" size="xs" variant="outline">Re-index</Button>
            <Button type="button" size="xs" variant="outline">Re-extract</Button>
          </div>
        </div>
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

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="flex flex-col gap-4 rounded border border-border bg-white p-8 shadow-sm md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Version history
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">{docPath}</h1>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            Compare immutable document versions, inspect technical state, and restore a prior head when needed.
          </p>
        </div>
        <Link
          to="/projects/$slug/docs/$"
          params={{ slug: projectSlug, _splat: docPath }}
          className="inline-flex h-8 items-center rounded border border-border bg-white px-3 text-sm font-medium transition-colors hover:bg-muted"
        >
          <ArrowLeft className="mr-1 size-4" />
          Back to document
        </Link>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.3fr)_minmax(0,0.7fr)]">
        <Card className="bg-white">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitCompareArrows className="size-4" />
              Compare and restore
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-sm">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                Base version
              </span>
              <select
                value={selectedA ?? ''}
                onChange={(event) => setSelectedA(Number(event.target.value))}
                className="mt-2 h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none"
              >
                {versions.map((version) => (
                  <option key={`base-${version.version_number}`} value={version.version_number}>
                    v{version.version_number.toString().padStart(3, '0')} · {version.branch}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                Target version
              </span>
              <select
                value={selectedB ?? ''}
                onChange={(event) => setSelectedB(Number(event.target.value))}
                className="mt-2 h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none"
              >
                {versions.map((version) => (
                  <option key={`target-${version.version_number}`} value={version.version_number}>
                    v{version.version_number.toString().padStart(3, '0')} · {version.branch}
                  </option>
                ))}
              </select>
            </label>

            <Separator />

            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="xs"
                variant={viewType === 'split' ? 'default' : 'outline'}
                onClick={() => setViewType('split')}
              >
                Split
              </Button>
              <Button
                type="button"
                size="xs"
                variant={viewType === 'unified' ? 'default' : 'outline'}
                onClick={() => setViewType('unified')}
              >
                Unified
              </Button>
            </div>

            <div className="space-y-2">
              {[...versions].reverse().map((version) => {
                const active =
                  version.version_number === selectedA || version.version_number === selectedB

                return (
                  <div
                    key={version.version_number}
                    className={`rounded border px-3 py-3 transition-colors ${
                      active
                        ? 'border-l-[3px] border-l-primary border-t-border border-r-border border-b-border bg-blue-50'
                        : 'border-border bg-muted'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedA(selectedB)
                        setSelectedB(version.version_number)
                      }}
                      className="w-full text-left"
                    >
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-mono">
                          v{version.version_number.toString().padStart(3, '0')}
                        </span>
                        <Badge variant="outline">{version.branch}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {new Date(version.created_at).toLocaleString()}
                      </div>
                    </button>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {version.label && <Badge variant="secondary">{version.label}</Badge>}
                      {version.restored_from && (
                        <Badge variant="outline">
                          restored from v{version.restored_from.toString().padStart(3, '0')}
                        </Badge>
                      )}
                    </div>

                    <details className="mt-3 rounded border border-border bg-white p-3 text-xs">
                      <summary className="cursor-pointer font-medium uppercase tracking-[0.2em] text-muted-foreground">
                        Technical panel
                      </summary>
                      <div className="mt-3 space-y-2 font-mono leading-5 text-muted-foreground">
                        <div>hash: {version.content_hash}</div>
                        <div>path: {docPath}</div>
                        <div>created_by: {version.created_by ?? version.change_source ?? 'unknown'}</div>
                        <div>indexing_status: {version.indexing_status ?? 'unknown'}</div>
                        <div>version_file: {version.version_file}</div>
                      </div>
                    </details>

                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      className="mt-3"
                      onClick={() => handleRestore(version.version_number)}
                      disabled={
                        restoreMutation.isPending &&
                        restoreMutation.variables === version.version_number
                      }
                    >
                      <RotateCcw className="size-3" />
                      {restoreMutation.isPending &&
                      restoreMutation.variables === version.version_number
                        ? 'Restoring…'
                        : 'Restore'}
                    </Button>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="min-w-0 bg-white">
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-3">
              <span>
                {selectedA != null && selectedB != null
                  ? `v${selectedA.toString().padStart(3, '0')} → v${selectedB.toString().padStart(3, '0')}`
                  : 'Choose versions'}
              </span>
              {diff && (
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="secondary">+{diff.additions}</Badge>
                  <Badge variant="outline">-{diff.deletions}</Badge>
                </div>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-auto">
            {selectedA === selectedB ? (
              <div className="rounded border border-dashed border-border px-6 py-10 text-sm text-muted-foreground">
                Select two different versions to compare.
              </div>
            ) : parsedDiff.length === 0 ? (
              <div className="rounded border border-dashed border-border px-6 py-10 text-sm text-muted-foreground">
                No diff available for the selected versions.
              </div>
            ) : (
              <div className="datum-diff-view overflow-hidden rounded border border-border bg-white">
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
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
