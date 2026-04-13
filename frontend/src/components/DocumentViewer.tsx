import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ChevronRight, History, PenSquare } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ContextPanel } from '@/components/ContextPanel'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useContextPanel } from '@/lib/context-panel'
import { api, type DocumentContent, type VersionInfo } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { extractHeadings } from '@/lib/technical-terms'

const CodeMirrorEditor = lazy(() =>
  import('@/components/CodeMirrorEditor').then((module) => ({
    default: module.CodeMirrorEditor,
  })),
)

interface DocumentViewerProps {
  projectSlug: string
  docPath: string
  sourceContext?: {
    query?: string
    snippet?: string
    heading?: string
    signals: string[]
  }
}

type ViewMode = 'rendered' | 'raw' | 'split' | 'edit'
const EMPTY_VERSIONS: VersionInfo[] = []

function detectLanguage(path: string): 'markdown' | 'json' | 'sql' | 'yaml' | 'text' {
  if (path.endsWith('.json')) {
    return 'json'
  }
  if (path.endsWith('.sql')) {
    return 'sql'
  }
  if (path.endsWith('.yaml') || path.endsWith('.yml')) {
    return 'yaml'
  }
  if (path.endsWith('.md')) {
    return 'markdown'
  }
  return 'text'
}

function buildBreadcrumbs(projectSlug: string, relativePath: string) {
  const segments = relativePath.split('/')
  const crumbs = [
    { label: projectSlug, path: null as string | null },
  ]
  let currentPath = ''
  for (const segment of segments) {
    currentPath = currentPath ? `${currentPath}/${segment}` : segment
    crumbs.push({
      label: segment,
      path: currentPath,
    })
  }
  return crumbs
}

export function DocumentViewer({ projectSlug, docPath, sourceContext }: DocumentViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('rendered')
  const [editContent, setEditContent] = useState('')
  const queryClient = useQueryClient()
  const { setContent } = useContextPanel()

  const documentQuery = useQuery({
    queryKey: queryKeys.document(projectSlug, docPath),
    queryFn: () => api.documents.get(projectSlug, docPath),
  })
  const versionsQuery = useQuery({
    queryKey: queryKeys.versions(projectSlug, docPath),
    queryFn: () => api.versions.list(projectSlug, docPath),
  })
  const document = documentQuery.data ?? null
  const versions = versionsQuery.data ?? EMPTY_VERSIONS

  useEffect(() => {
    if (documentQuery.data) {
      setEditContent(documentQuery.data.content)
    }
  }, [documentQuery.data?.content, docPath, projectSlug])

  useEffect(() => {
    const handleEnterEdit = () => setViewMode('edit')
    const handleExitEdit = () =>
      setViewMode((current) => (current === 'edit' || current === 'split' ? 'rendered' : current))

    window.addEventListener('datum:enter-edit-mode', handleEnterEdit)
    window.addEventListener('datum:exit-edit-mode', handleExitEdit)
    return () => {
      window.removeEventListener('datum:enter-edit-mode', handleEnterEdit)
      window.removeEventListener('datum:exit-edit-mode', handleExitEdit)
    }
  }, [])

  const displayContent =
    viewMode === 'split' || viewMode === 'edit' ? editContent : document?.content ?? ''
  const headings = useMemo(() => extractHeadings(displayContent), [displayContent])

  useEffect(() => {
    if (document) {
      setContent(
        <ContextPanel
          projectSlug={projectSlug}
          document={document.metadata}
          versions={versions}
          headings={headings}
        />,
      )
    }
    return () => setContent(null)
  }, [document, headings, projectSlug, setContent, versions])

  const saveMutation = useMutation({
    mutationFn: async (nextContent: string) => {
      if (!document) {
        throw new Error('Document missing')
      }
      return api.documents.save(projectSlug, document.metadata.relative_path, {
        content: nextContent,
        base_hash: document.metadata.content_hash,
      })
    },
    onMutate: async (nextContent) => {
      if (!document) {
        return { previousDocument: null as DocumentContent | null }
      }

      const documentKey = queryKeys.document(projectSlug, document.metadata.relative_path)
      await queryClient.cancelQueries({ queryKey: documentKey })
      const previousDocument =
        queryClient.getQueryData<DocumentContent>(documentKey) ?? null

      queryClient.setQueryData<DocumentContent>(documentKey, {
        content: nextContent,
        metadata: previousDocument?.metadata ?? document.metadata,
      })

      return { previousDocument }
    },
    onError: (error, _nextContent, context) => {
      if (document) {
        queryClient.setQueryData(
          queryKeys.document(projectSlug, document.metadata.relative_path),
          context?.previousDocument ?? null,
        )
      }

      const message = error instanceof Error ? error.message : String(error)
      if (message.includes('409')) {
        alert('Document was modified externally. Reload the latest cabinet state and try again.')
      } else {
        alert(message)
      }
    },
    onSuccess: async (metadata, nextContent) => {
      const documentKey = queryKeys.document(projectSlug, metadata.relative_path)
      queryClient.setQueryData<DocumentContent>(documentKey, {
        content: nextContent,
        metadata,
      })
      setEditContent(nextContent)
      setViewMode('rendered')

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.versions(projectSlug, metadata.relative_path) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectSlug) }),
      ])
    },
  })

  const handleSave = async () => {
    if (!document) {
      return
    }
    await saveMutation.mutateAsync(editContent)
  }

  if (documentQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading document…</div>
  }

  if (!document) {
    return <div className="p-8 text-muted-foreground">Document not found.</div>
  }

  const { metadata } = document
  const language = detectLanguage(metadata.relative_path)
  const breadcrumbs = buildBreadcrumbs(projectSlug, metadata.relative_path)
  const historySplat = `${metadata.relative_path}/history`
  const showSearchSource = Boolean(sourceContext?.query && viewMode !== 'edit' && viewMode !== 'split')

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <nav className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {breadcrumbs.map((crumb, index) => (
                <div key={`${crumb.label}:${crumb.path ?? 'project'}`} className="flex items-center gap-2">
                  {index > 0 && <ChevronRight className="size-3 text-muted-foreground/60" />}
                  <Link
                    to={index === 0 ? '/projects/$slug' : '/projects/$slug/docs/$'}
                    params={
                      index === 0
                        ? { slug: projectSlug }
                        : { slug: projectSlug, _splat: crumb.path ?? metadata.relative_path }
                    }
                    className="truncate rounded-full px-2 py-0.5 transition-colors hover:bg-accent"
                  >
                    {crumb.label}
                  </Link>
                </div>
              ))}
            </nav>

            <h1 className="mt-4 text-3xl font-semibold tracking-tight">{metadata.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{metadata.doc_type}</Badge>
              <Badge variant="outline">{metadata.status}</Badge>
              <Badge variant="outline">v{metadata.version}</Badge>
              {metadata.tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(['rendered', 'raw', 'split', 'edit'] as const).map((mode) => (
              <Button
                key={mode}
                type="button"
                variant={viewMode === mode ? 'default' : 'outline'}
                size="sm"
                onClick={() => setViewMode(mode)}
              >
                {mode}
              </Button>
            ))}
            <Link
              to="/projects/$slug/docs/$"
              params={{ slug: projectSlug, _splat: historySplat }}
              className="inline-flex h-8 items-center rounded-lg border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
            >
              <History className="mr-1 size-4" />
              History
            </Link>
            <Button type="button" variant="outline" size="sm" onClick={() => setViewMode('edit')}>
              <PenSquare className="mr-1 size-4" />
              Edit
              <kbd className="ml-1 rounded border px-1 py-0.5 text-[10px] text-muted-foreground">
                E
              </kbd>
            </Button>
            {(viewMode === 'edit' || viewMode === 'split') && (
              <Button type="button" size="sm" onClick={handleSave} disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving…' : 'Save'}
              </Button>
            )}
          </div>
        </div>
      </div>

      {viewMode === 'edit' && (
        <CardShell>
          <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading editor…</div>}>
            <CodeMirrorEditor
              value={editContent}
              onChange={setEditContent}
              onSave={handleSave}
              language={language}
            />
          </Suspense>
        </CardShell>
      )}

      {viewMode === 'split' && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)]">
          <CardShell title="Source">
            <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading editor…</div>}>
              <CodeMirrorEditor
                value={editContent}
                onChange={setEditContent}
                onSave={handleSave}
                language={language}
              />
            </Suspense>
          </CardShell>
          <CardShell title={language === 'markdown' ? 'Rendered preview' : 'Rendered source'}>
            {language === 'markdown' ? (
              <MarkdownRenderer content={editContent} projectSlug={projectSlug} />
            ) : (
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
                {editContent}
              </pre>
            )}
          </CardShell>
        </div>
      )}

      {viewMode === 'rendered' && (
        <div className={showSearchSource ? 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]' : ''}>
          <CardShell>
            {language === 'markdown' ? (
              <MarkdownRenderer content={document.content} projectSlug={projectSlug} />
            ) : (
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
                {document.content}
              </pre>
            )}
          </CardShell>
          {showSearchSource && sourceContext && (
            <SearchSourceCard
              query={sourceContext.query ?? ''}
              snippet={sourceContext.snippet ?? ''}
              heading={sourceContext.heading}
              signals={sourceContext.signals}
            />
          )}
        </div>
      )}

      {viewMode === 'raw' && (
        <div className={showSearchSource ? 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]' : ''}>
          <CardShell title="Raw document">
            <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
              {document.content}
            </pre>
          </CardShell>
          {showSearchSource && sourceContext && (
            <SearchSourceCard
              query={sourceContext.query ?? ''}
              snippet={sourceContext.snippet ?? ''}
              heading={sourceContext.heading}
              signals={sourceContext.signals}
            />
          )}
        </div>
      )}

      {headings.length > 0 && (
        <div className="rounded-[2rem] border border-border/80 bg-card/60 p-5 shadow-sm">
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Outline
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {headings.map((heading) => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                className="rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-sm transition-colors hover:bg-accent/50"
                style={{ paddingLeft: `${0.75 + (heading.level - 1) * 0.5}rem` }}
              >
                {heading.text}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SearchSourceCard({
  query,
  snippet,
  heading,
  signals,
}: {
  query: string
  snippet: string
  heading?: string
  signals: string[]
}) {
  return (
    <CardShell title="Search source">
      <div className="space-y-4 text-sm">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Query
          </div>
          <div className="mt-2 rounded-xl border border-border/70 bg-background/70 px-3 py-2 font-mono text-xs">
            {query}
          </div>
        </div>
        {heading && (
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Heading
            </div>
            <div className="mt-2 text-sm text-foreground/85">{heading}</div>
          </div>
        )}
        {signals.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {signals.map((signal) => (
              <Badge key={signal} variant="secondary">
                {signal}
              </Badge>
            ))}
          </div>
        )}
        <div className="rounded-2xl border border-border/70 bg-background/70 px-4 py-4 leading-6 text-foreground/85">
          {snippet}
        </div>
      </div>
    </CardShell>
  )
}

function CardShell({
  children,
  title,
}: {
  children: ReactNode
  title?: string
}) {
  return (
    <div className="rounded-[2rem] border border-border/80 bg-card/80 p-5 shadow-sm">
      {title && (
        <div className="mb-4 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          {title}
        </div>
      )}
      {children}
    </div>
  )
}
