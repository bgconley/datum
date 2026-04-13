import { Link } from '@tanstack/react-router'
import { Clock3, History, Tags } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import type { DocumentMeta, VersionInfo } from '@/lib/api'

interface ContextPanelProps {
  projectSlug: string
  document: DocumentMeta
  versions: VersionInfo[]
}

export function ContextPanel({ projectSlug, document, versions }: ContextPanelProps) {
  const recentVersions = [...versions].slice(-5).reverse()

  return (
    <ScrollArea className="h-full">
      <div className="space-y-5 p-5">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Context
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">{document.title}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{document.doc_type}</Badge>
            <Badge variant="outline">{document.status}</Badge>
            <Badge variant="outline">v{document.version}</Badge>
          </div>
        </div>

        <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Cabinet path
          </div>
          <div className="mt-2 font-mono text-xs leading-6 text-foreground/80">
            {document.relative_path}
          </div>
        </div>

        {document.tags.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              <Tags className="size-3.5" />
              Tags
            </div>
            <div className="flex flex-wrap gap-2">
              {document.tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <Separator />

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              <History className="size-3.5" />
              Recent versions
            </div>
            <Link
              to="/projects/$slug/history/$"
              params={{ slug: projectSlug, _splat: document.relative_path }}
              className="inline-flex h-6 items-center rounded-lg border border-border bg-background px-2 text-xs font-medium transition-colors hover:bg-muted"
            >
              Full history
            </Link>
          </div>
          <div className="space-y-2">
            {recentVersions.length === 0 ? (
              <div className="text-sm text-muted-foreground">No version history yet.</div>
            ) : (
              recentVersions.map((version) => (
                <div
                  key={`${version.branch}:${version.version_number}`}
                  className="rounded-xl border border-border/70 bg-background/70 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-mono text-sm">
                      v{version.version_number.toString().padStart(3, '0')}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {version.change_source ?? 'unknown'}
                    </div>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock3 className="size-3" />
                    {new Date(version.created_at).toLocaleString()}
                  </div>
                  {version.label && (
                    <div className="mt-2">
                      <Badge variant="secondary">{version.label}</Badge>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <Separator />

        <details className="rounded-2xl border border-border/70 bg-background/60 p-4 text-xs">
          <summary className="cursor-pointer font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Technical details
          </summary>
          <div className="mt-3 space-y-2 font-mono text-[11px] leading-5 text-muted-foreground">
            <div>hash: {document.content_hash}</div>
            <div>uid: {document.document_uid}</div>
            <div>created: {document.created ?? 'unknown'}</div>
            <div>updated: {document.updated ?? 'unknown'}</div>
          </div>
        </details>
      </div>
    </ScrollArea>
  )
}
