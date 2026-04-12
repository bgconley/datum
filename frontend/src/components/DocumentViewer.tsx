import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, type DocumentContent } from '@/lib/api'

interface DocumentViewerProps {
  projectSlug: string
  docPath: string
}

export function DocumentViewer({ projectSlug, docPath }: DocumentViewerProps) {
  const [doc, setDoc] = useState<DocumentContent | null>(null)
  const [viewMode, setViewMode] = useState<'rendered' | 'raw' | 'split'>('rendered')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.documents
      .get(projectSlug, docPath)
      .then(setDoc)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [projectSlug, docPath])

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>
  if (!doc) return <div className="p-8 text-muted-foreground">Document not found</div>

  const { metadata } = doc
  // Strip frontmatter from display content
  const displayContent = doc.content.replace(/^---[\s\S]*?---\n*/, '')

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="mb-6">
        <div className="text-sm text-muted-foreground mb-1">
          {docPath}
        </div>
        <h1 className="text-2xl font-bold mb-2">{metadata.title}</h1>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{metadata.doc_type}</Badge>
          <Badge variant="outline">{metadata.status}</Badge>
          <span className="text-sm text-muted-foreground">v{metadata.version}</span>
          {metadata.tags?.map((t) => (
            <Badge key={t} variant="outline" className="text-xs">
              {t}
            </Badge>
          ))}
        </div>
      </div>

      {/* View mode toggle */}
      <div className="flex gap-1 mb-4 border-b border-border pb-2">
        {(['rendered', 'raw', 'split'] as const).map((mode) => (
          <Button
            key={mode}
            variant={viewMode === mode ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode(mode)}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </Button>
        ))}
      </div>

      {/* Content */}
      <div className={viewMode === 'split' ? 'grid grid-cols-2 gap-4' : ''}>
        {(viewMode === 'rendered' || viewMode === 'split') && (
          <div className="prose prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {displayContent}
            </ReactMarkdown>
          </div>
        )}
        {(viewMode === 'raw' || viewMode === 'split') && (
          <pre className="bg-muted p-4 rounded-lg text-sm overflow-auto font-mono whitespace-pre-wrap">
            {doc.content}
          </pre>
        )}
      </div>
    </div>
  )
}
