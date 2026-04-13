import { lazy, Suspense, type ReactNode, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ContextPanel } from '@/components/ContextPanel'
import { useContextPanel } from '@/lib/context-panel'
import { api, type DocumentContent, type VersionInfo } from '@/lib/api'

const CodeMirrorEditor = lazy(() =>
  import('@/components/CodeMirrorEditor').then((module) => ({
    default: module.CodeMirrorEditor,
  })),
)

interface DocumentViewerProps {
  projectSlug: string
  docPath: string
}

type ViewMode = 'rendered' | 'raw' | 'split' | 'edit'

function stripFrontmatter(content: string): string {
  return content.replace(/^---[\s\S]*?---\n*/, '')
}

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

export function DocumentViewer({ projectSlug, docPath }: DocumentViewerProps) {
  const [document, setDocument] = useState<DocumentContent | null>(null)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [viewMode, setViewMode] = useState<ViewMode>('rendered')
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const { setContent } = useContextPanel()

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.documents.get(projectSlug, docPath),
      api.versions.list(projectSlug, docPath).catch(() => []),
    ])
      .then(([nextDocument, nextVersions]) => {
        setDocument(nextDocument)
        setVersions(nextVersions)
        setEditContent(nextDocument.content)
      })
      .catch((error) => {
        console.error(error)
        setDocument(null)
        setVersions([])
      })
      .finally(() => setLoading(false))
  }, [docPath, projectSlug])

  useEffect(() => {
    if (document) {
      setContent(
        <ContextPanel
          projectSlug={projectSlug}
          document={document.metadata}
          versions={versions}
        />,
      )
    }
    return () => setContent(null)
  }, [document, projectSlug, setContent, versions])

  const handleSave = async () => {
    if (!document) {
      return
    }

    setSaving(true)
    try {
      await api.documents.save(projectSlug, document.metadata.relative_path, {
        content: editContent,
        base_hash: document.metadata.content_hash,
      })

      const [nextDocument, nextVersions] = await Promise.all([
        api.documents.get(projectSlug, document.metadata.relative_path),
        api.versions.list(projectSlug, document.metadata.relative_path).catch(() => []),
      ])
      setDocument(nextDocument)
      setVersions(nextVersions)
      setEditContent(nextDocument.content)
      setViewMode('rendered')
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      if (message.includes('409')) {
        alert('Document was modified externally. Reload the latest cabinet state and try again.')
      } else {
        alert(message)
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading document…</div>
  }

  if (!document) {
    return <div className="p-8 text-muted-foreground">Document not found.</div>
  }

  const { metadata } = document
  const language = detectLanguage(metadata.relative_path)
  const renderedSource =
    viewMode === 'split' || viewMode === 'edit'
      ? stripFrontmatter(editContent)
      : stripFrontmatter(document.content)

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="rounded-[2rem] border border-border/80 bg-card/80 p-8 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
              {metadata.relative_path}
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">{metadata.title}</h1>
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
              to="/projects/$slug/history/$"
              params={{ slug: projectSlug, _splat: metadata.relative_path }}
              className="inline-flex h-8 items-center rounded-lg border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
            >
              History
            </Link>
            {(viewMode === 'edit' || viewMode === 'split') && (
              <Button type="button" size="sm" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
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
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
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
          <CardShell title={language === 'markdown' ? 'Preview' : 'Rendered source'}>
            {language === 'markdown' ? (
              <div className="datum-prose">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{renderedSource}</ReactMarkdown>
              </div>
            ) : (
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
                {editContent}
              </pre>
            )}
          </CardShell>
        </div>
      )}

      {viewMode === 'rendered' && (
        <CardShell>
          {language === 'markdown' ? (
            <div className="datum-prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{renderedSource}</ReactMarkdown>
            </div>
          ) : (
            <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
              {document.content}
            </pre>
          )}
        </CardShell>
      )}

      {viewMode === 'raw' && (
        <CardShell>
          <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
            {document.content}
          </pre>
        </CardShell>
      )}
    </div>
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
