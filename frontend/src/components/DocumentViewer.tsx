import { useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, type DocumentContent } from '@/lib/api'

interface DocumentViewerProps {
  projectSlug: string
  docPath: string
}

type ViewMode = 'rendered' | 'raw' | 'split' | 'edit'

export function DocumentViewer({ projectSlug, docPath }: DocumentViewerProps) {
  const [doc, setDoc] = useState<DocumentContent | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('rendered')
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadDoc = useCallback(() => {
    setLoading(true)
    api.documents
      .get(projectSlug, docPath)
      .then((d) => {
        setDoc(d)
        // Edit mode works with the full file content (frontmatter included)
        // for round-trip fidelity — what GET returns is what PUT accepts
        setEditContent(d.content)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [projectSlug, docPath])

  useEffect(() => { loadDoc() }, [loadDoc])

  const handleSave = async () => {
    if (!doc) return
    setSaving(true)
    try {
      // Send full file content (frontmatter + body) — the API expects this
      await api.documents.save(projectSlug, docPath, {
        content: editContent,
        base_hash: doc.metadata.content_hash,
      })
      setViewMode('rendered')
      loadDoc() // Reload to get new version/hash
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.includes('409')) {
        alert('Document was modified externally. Please reload and try again.')
      } else {
        alert(msg)
      }
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault()
      if (viewMode === 'edit') handleSave()
    }
  }

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>
  if (!doc) return <div className="p-8 text-muted-foreground">Document not found</div>

  const { metadata } = doc
  const displayContent = doc.content.replace(/^---[\s\S]*?---\n*/, '')

  return (
    <div className="max-w-4xl mx-auto p-8" onKeyDown={handleKeyDown}>
      {/* Header */}
      <div className="mb-6">
        <div className="text-sm text-muted-foreground mb-1">{docPath}</div>
        <h1 className="text-2xl font-bold mb-2">{metadata.title}</h1>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{metadata.doc_type}</Badge>
          <Badge variant="outline">{metadata.status}</Badge>
          <span className="text-sm text-muted-foreground">v{metadata.version}</span>
          {metadata.tags?.map((t) => (
            <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
          ))}
        </div>
      </div>

      {/* View mode toggle */}
      <div className="flex gap-1 mb-4 border-b border-border pb-2">
        {(['rendered', 'raw', 'split', 'edit'] as const).map((mode) => (
          <Button
            key={mode}
            variant={viewMode === mode ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode(mode)}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </Button>
        ))}
        {viewMode === 'edit' && (
          <Button size="sm" variant="default" onClick={handleSave} disabled={saving} className="ml-auto">
            {saving ? 'Saving...' : 'Save (Ctrl+S)'}
          </Button>
        )}
      </div>

      {/* Content */}
      {viewMode === 'edit' ? (
        <Textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="font-mono text-sm min-h-[500px] resize-y"
          spellCheck={false}
        />
      ) : (
        <div className={viewMode === 'split' ? 'grid grid-cols-2 gap-4' : ''}>
          {(viewMode === 'rendered' || viewMode === 'split') && (
            <div className="prose prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
            </div>
          )}
          {(viewMode === 'raw' || viewMode === 'split') && (
            <pre className="bg-muted p-4 rounded-lg text-sm overflow-auto font-mono whitespace-pre-wrap">
              {doc.content}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
