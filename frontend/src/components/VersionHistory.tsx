import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowLeft, GitCompareArrows } from 'lucide-react'
import { Diff, Hunk, parseDiff } from 'react-diff-view'
import 'react-diff-view/style/index.css'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useContextPanel } from '@/lib/context-panel'
import { api, type VersionDiff, type VersionInfo } from '@/lib/api'

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
  return (
    <div className="space-y-5 p-5">
      <div>
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Compare state
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">Version history</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Compare immutable cabinet versions to inspect how a document evolved over time.
        </p>
      </div>

      <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Selected comparison
        </div>
        <div className="mt-3 space-y-2 text-sm">
          <div>Base: {selectedA ? `v${selectedA.toString().padStart(3, '0')}` : 'Not selected'}</div>
          <div>Target: {selectedB ? `v${selectedB.toString().padStart(3, '0')}` : 'Not selected'}</div>
          {diff && (
            <div className="flex items-center gap-3 text-xs">
              <Badge variant="secondary">+{diff.additions}</Badge>
              <Badge variant="outline">-{diff.deletions}</Badge>
            </div>
          )}
        </div>
      </div>

      <Separator />

      <div className="space-y-2">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Available versions
        </div>
        <div className="space-y-2">
          {[...versions].reverse().map((version) => (
            <div
              key={version.version_number}
              className="rounded-xl border border-border/70 bg-background/70 px-3 py-2"
            >
              <div className="flex items-center justify-between text-sm">
                <span className="font-mono">
                  v{version.version_number.toString().padStart(3, '0')}
                </span>
                <span className="text-xs text-muted-foreground">
                  {version.change_source ?? 'unknown'}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {new Date(version.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

interface VersionHistoryProps {
  projectSlug: string
  docPath: string
}

export function VersionHistory({ projectSlug, docPath }: VersionHistoryProps) {
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [selectedA, setSelectedA] = useState<number | null>(null)
  const [selectedB, setSelectedB] = useState<number | null>(null)
  const [diff, setDiff] = useState<VersionDiff | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewType, setViewType] = useState<'split' | 'unified'>('split')
  const { setContent } = useContextPanel()

  useEffect(() => {
    setLoading(true)
    api.versions
      .list(projectSlug, docPath)
      .then((nextVersions) => {
        setVersions(nextVersions)
        if (nextVersions.length >= 2) {
          setSelectedA(nextVersions.at(-2)?.version_number ?? null)
          setSelectedB(nextVersions.at(-1)?.version_number ?? null)
        } else if (nextVersions.length === 1) {
          setSelectedA(nextVersions[0].version_number)
          setSelectedB(nextVersions[0].version_number)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [docPath, projectSlug])

  useEffect(() => {
    if (selectedA == null || selectedB == null || selectedA === selectedB) {
      setDiff(null)
      return
    }

    api.versions
      .diff(projectSlug, docPath, selectedA, selectedB)
      .then(setDiff)
      .catch(console.error)
  }, [docPath, projectSlug, selectedA, selectedB])

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

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading version history…</div>
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="flex flex-col gap-4 rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Version history
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">{docPath}</h1>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            Compare immutable document versions with split or unified diff rendering.
          </p>
        </div>
        <Link
          to="/projects/$slug/docs/$"
          params={{ slug: projectSlug, _splat: docPath }}
          className="inline-flex h-8 items-center rounded-lg border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
        >
          <ArrowLeft />
          Back to document
        </Link>
      </div>

      <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <Card className="bg-card/80">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitCompareArrows className="size-4" />
              Compare
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
                    v{version.version_number.toString().padStart(3, '0')}
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
                    v{version.version_number.toString().padStart(3, '0')}
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
                  <button
                    key={version.version_number}
                    type="button"
                    onClick={() => {
                      setSelectedA(selectedB)
                      setSelectedB(version.version_number)
                    }}
                    className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
                      active
                        ? 'border-foreground/20 bg-accent'
                        : 'border-border/70 bg-background/70 hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-mono">
                        v{version.version_number.toString().padStart(3, '0')}
                      </span>
                      {version.label && <Badge variant="secondary">{version.label}</Badge>}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {new Date(version.created_at).toLocaleString()}
                    </div>
                  </button>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="min-w-0 bg-card/80">
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
              <div className="rounded-2xl border border-dashed border-border px-6 py-10 text-sm text-muted-foreground">
                Select two different versions to compare.
              </div>
            ) : parsedDiff.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border px-6 py-10 text-sm text-muted-foreground">
                No diff available for the selected versions.
              </div>
            ) : (
              <div className="datum-diff-view overflow-hidden rounded-2xl border border-border/70 bg-background/85">
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
