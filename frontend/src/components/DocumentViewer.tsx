import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ChevronRight, FolderPlus, History, PenSquare, Trash2 } from 'lucide-react'
import { Document as PdfDocument, Page as PdfPage, pdfjs } from 'react-pdf'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ContextPanel } from '@/components/ContextPanel'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useContextPanel } from '@/lib/context-panel'
import {
  api,
  type AnnotationItem,
  type CollectionItem,
  type DocumentContent,
  type VersionInfo,
} from '@/lib/api'
import { notify } from '@/lib/notifications'
import { queryKeys } from '@/lib/query-keys'
import { extractHeadings } from '@/lib/technical-terms'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker

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
    queryLabel?: string
    snippet?: string
    heading?: string
    signals: string[]
    versionNumber?: number
    startChar?: number
    endChar?: number
    chunkId?: string
  }
}

type ViewMode = 'rendered' | 'raw' | 'split' | 'edit'
const EMPTY_VERSIONS: VersionInfo[] = []

type DocumentMediaKind = 'text' | 'pdf' | 'image'

function detectLanguage(
  path: string,
): 'markdown' | 'json' | 'sql' | 'yaml' | 'typescript' | 'javascript' | 'toml' | 'prisma' | 'text' {
  if (path.endsWith('.json')) {
    return 'json'
  }
  if (path.endsWith('.sql')) {
    return 'sql'
  }
  if (path.endsWith('.yaml') || path.endsWith('.yml')) {
    return 'yaml'
  }
  if (path.endsWith('.ts') || path.endsWith('.tsx')) {
    return 'typescript'
  }
  if (path.endsWith('.js') || path.endsWith('.jsx')) {
    return 'javascript'
  }
  if (path.endsWith('.toml')) {
    return 'toml'
  }
  if (path.endsWith('.prisma')) {
    return 'prisma'
  }
  if (path.endsWith('.md')) {
    return 'markdown'
  }
  return 'text'
}

function detectMediaKind(path: string, contentKind: DocumentContent['content_kind']): DocumentMediaKind {
  if (contentKind === 'binary' && path.endsWith('.pdf')) {
    return 'pdf'
  }
  if (
    contentKind === 'binary' &&
    ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].some((extension) => path.endsWith(extension))
  ) {
    return 'image'
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
  const [pdfPageCount, setPdfPageCount] = useState(0)
  const [editContent, setEditContent] = useState('')
  const [annotationType, setAnnotationType] = useState<'comment' | 'highlight' | 'pin'>('comment')
  const [annotationContent, setAnnotationContent] = useState('')
  const [annotationStart, setAnnotationStart] = useState('')
  const [annotationEnd, setAnnotationEnd] = useState('')
  const [selectedCollectionId, setSelectedCollectionId] = useState('')
  const [newCollectionName, setNewCollectionName] = useState('')
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
  const annotationsQuery = useQuery({
    queryKey: document?.metadata.version_id
      ? queryKeys.annotations(document.metadata.version_id)
      : ['annotations', 'idle'],
    queryFn: () => api.annotations.list(document!.metadata.version_id!),
    enabled: Boolean(document?.metadata.version_id),
  })
  const collectionsQuery = useQuery({
    queryKey: queryKeys.collections(projectSlug),
    queryFn: () => api.collections.list(projectSlug),
    enabled: Boolean(projectSlug),
  })
  const membershipsQuery = useQuery({
    queryKey: queryKeys.documentCollections(projectSlug, document?.metadata.document_uid ?? 'idle'),
    queryFn: () => api.collections.forDocument(projectSlug, document!.metadata.document_uid),
    enabled: Boolean(projectSlug && document?.metadata.document_uid),
  })
  const documentEntitiesQuery = useQuery({
    queryKey: queryKeys.documentEntities(projectSlug, docPath),
    queryFn: () => api.documents.entities(projectSlug, docPath),
    enabled: Boolean(projectSlug && docPath),
  })
  const annotations = annotationsQuery.data ?? []
  const collections = collectionsQuery.data ?? []
  const documentCollections = membershipsQuery.data ?? []
  const documentEntities = documentEntitiesQuery.data ?? []

  useEffect(() => {
    if (documentQuery.data) {
      setEditContent(documentQuery.data.content)
    }
  }, [documentQuery.data?.content, docPath, projectSlug])

  useEffect(() => {
    if (!documentQuery.data) {
      return
    }
    const mediaKind = detectMediaKind(
      documentQuery.data.metadata.relative_path,
      documentQuery.data.content_kind,
    )
    if (mediaKind !== 'text' && (viewMode === 'split' || viewMode === 'edit')) {
      setViewMode('rendered')
    }
  }, [documentQuery.data, viewMode])

  useEffect(() => {
    if (!selectedCollectionId && collections.length > 0) {
      setSelectedCollectionId(collections[0].id)
    }
  }, [collections, selectedCollectionId])

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
        notify('Document was modified externally. Reload the latest cabinet state and try again.')
      } else {
        notify(message)
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

  const createAnnotationMutation = useMutation({
    mutationFn: async () => {
      if (!document?.metadata.version_id) {
        throw new Error('Document version is unavailable for annotations.')
      }

      const parseNumber = (value: string) => {
        const trimmed = value.trim()
        return trimmed ? Number(trimmed) : null
      }

      return api.annotations.create({
        version_id: document.metadata.version_id,
        annotation_type: annotationType,
        content: annotationContent.trim() || null,
        start_char: parseNumber(annotationStart),
        end_char: parseNumber(annotationEnd),
      })
    },
    onSuccess: async () => {
      if (!document?.metadata.version_id) {
        return
      }
      setAnnotationContent('')
      setAnnotationStart('')
      setAnnotationEnd('')
      await queryClient.invalidateQueries({
        queryKey: queryKeys.annotations(document.metadata.version_id),
      })
    },
  })

  const deleteAnnotationMutation = useMutation({
    mutationFn: async (annotationId: string) => api.annotations.delete(annotationId),
    onSuccess: async () => {
      if (!document?.metadata.version_id) {
        return
      }
      await queryClient.invalidateQueries({
        queryKey: queryKeys.annotations(document.metadata.version_id),
      })
    },
  })

  const addToCollectionMutation = useMutation({
    mutationFn: async (collectionId: string) => {
      if (!document) {
        throw new Error('Document missing')
      }
      return api.collections.addMember(projectSlug, collectionId, {
        document_uid: document.metadata.document_uid,
      })
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.collections(projectSlug) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.documentCollections(
            projectSlug,
            document?.metadata.document_uid ?? 'idle',
          ),
        }),
      ])
    },
  })

  const removeFromCollectionMutation = useMutation({
    mutationFn: async (collectionId: string) => {
      if (!document) {
        throw new Error('Document missing')
      }
      return api.collections.removeMember(projectSlug, collectionId, document.metadata.document_uid)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.collections(projectSlug) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.documentCollections(
            projectSlug,
            document?.metadata.document_uid ?? 'idle',
          ),
        }),
      ])
    },
  })

  const createCollectionMutation = useMutation({
    mutationFn: async () => {
      const name = newCollectionName.trim()
      if (!name) {
        throw new Error('Collection name is required.')
      }
      const created = await api.collections.create(projectSlug, { name })
      if (document) {
        await api.collections.addMember(projectSlug, created.id, {
          document_uid: document.metadata.document_uid,
        })
      }
      return created
    },
    onSuccess: async (collection) => {
      setNewCollectionName('')
      setSelectedCollectionId(collection.id)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.collections(projectSlug) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.documentCollections(
            projectSlug,
            document?.metadata.document_uid ?? 'idle',
          ),
        }),
      ])
    },
  })

  const handleSave = async () => {
    if (!document) {
      return
    }
    await saveMutation.mutateAsync(editContent)
  }

  const handleCreateAnnotation = async () => {
    try {
      await createAnnotationMutation.mutateAsync()
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error))
    }
  }

  const handleAddToCollection = async () => {
    if (!selectedCollectionId) {
      notify('Choose a collection first.')
      return
    }
    try {
      await addToCollectionMutation.mutateAsync(selectedCollectionId)
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error))
    }
  }

  const handleCreateCollection = async () => {
    try {
      await createCollectionMutation.mutateAsync()
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error))
    }
  }

  if (documentQuery.isLoading) {
    return <div className="p-8 text-muted-foreground">Loading document…</div>
  }

  if (!document) {
    return <div className="p-8 text-muted-foreground">Document not found.</div>
  }

  const { metadata } = document
  const language = detectLanguage(metadata.relative_path)
  const mediaKind = detectMediaKind(metadata.relative_path, document.content_kind)
  const assetUrl = document.asset_url ?? api.documents.assetUrl(projectSlug, metadata.relative_path)
  const availableViewModes =
    mediaKind === 'text'
      ? (['rendered', 'raw', 'split', 'edit'] as const)
      : (['rendered', 'raw'] as const)
  const breadcrumbs = buildBreadcrumbs(projectSlug, metadata.relative_path)
  const historySplat = `${metadata.relative_path}/history`
  const showSearchSource =
    Boolean(
      (
        sourceContext?.query ||
        sourceContext?.snippet ||
        sourceContext?.heading ||
        sourceContext?.versionNumber != null ||
        sourceContext?.startChar != null ||
        sourceContext?.endChar != null ||
        sourceContext?.chunkId
      ) &&
        viewMode !== 'edit' &&
        viewMode !== 'split',
    )

  return (
    <div className="flex flex-col gap-[12px] overflow-auto px-[24px] py-[20px]">
      {/* Breadcrumbs — Figma: text-[11px], folders #666, sep #999, file #333 medium */}
      <nav className="flex items-center gap-[4px] text-[11px]">
        {breadcrumbs.map((crumb, index) => (
          <div key={`${crumb.label}:${crumb.path ?? 'project'}`} className="flex items-center gap-[4px]">
            {index > 0 && <span className="text-[#999]">/</span>}
            <Link
              to={index === 0 ? '/projects/$slug' : '/projects/$slug/docs/$'}
              params={
                index === 0
                  ? { slug: projectSlug }
                  : { slug: projectSlug, _splat: crumb.path ?? metadata.relative_path }
              }
              className={index === breadcrumbs.length - 1 ? 'font-medium text-[#333]' : 'text-[#666] hover:text-[#333]'}
            >
              {crumb.label}
            </Link>
          </div>
        ))}
      </nav>

      {/* Title row + controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[12px]">
          <h1 className="text-[18px] font-semibold text-[#1b2431]">{metadata.title}</h1>
          {(viewMode === 'edit' || viewMode === 'split') && (
            <span className="text-[13px] text-[#999]">(Editing)</span>
          )}
          {metadata.status === 'approved' ? (
            <span className="rounded-[3px] bg-[#5cb85c] px-[8px] py-[3px] text-[10px] font-semibold text-white">
              Approved
            </span>
          ) : (
            <span className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[10px] font-semibold text-[#333]">
              {metadata.status}
            </span>
          )}
          {metadata.tags.map((tag) => (
            <span key={tag} className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[10px] font-semibold text-[#333]">
              {tag}
            </span>
          ))}
          <span className="rounded-[3px] bg-[#e1e8ed] px-[8px] py-[3px] text-[10px] font-semibold text-[#333]">
            v{metadata.version}
          </span>
        </div>

        {/* View mode controls — Figma: individual buttons, active=bg-[#333], EDIT=bg-[#22a5f1] */}
        <div className="flex items-center gap-[8px]">
          {availableViewModes
            .filter((mode) => mode !== 'edit')
            .map((mode) => (
              <button
                key={mode}
                type="button"
                className={`rounded-[4px] border border-[#e1e8ed] px-[10px] py-[6px] text-[10px] font-semibold uppercase ${
                  viewMode === mode
                    ? 'bg-[#333] text-white'
                    : 'bg-white text-[#333] hover:bg-[#f7f9fa]'
                }`}
                onClick={() => setViewMode(mode)}
              >
                {mode === 'raw' ? 'SOURCE' : mode}
              </button>
            ))}
          <Link
            to="/projects/$slug/docs/$"
            params={{ slug: projectSlug, _splat: historySplat }}
            className="rounded-[4px] border border-[#e1e8ed] bg-white px-[10px] py-[6px] text-[10px] font-semibold uppercase text-[#333] hover:bg-[#f7f9fa]"
          >
            HISTORY
          </Link>
          {mediaKind === 'text' && (
            <button
              type="button"
              className="rounded-[4px] bg-[#22a5f1] px-[16px] py-[6px] text-[10px] font-semibold uppercase text-white hover:bg-[#22a5f1]/90"
              onClick={() => setViewMode('edit')}
            >
              EDIT
            </button>
          )}
          {mediaKind === 'text' && (viewMode === 'edit' || viewMode === 'split') && (
            <button
              type="button"
              className="rounded-[4px] bg-[#22a5f1] px-[16px] py-[6px] text-[10px] font-semibold uppercase text-white hover:bg-[#22a5f1]/90"
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {mediaKind === 'text' && viewMode === 'edit' && (
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

      {mediaKind === 'text' && viewMode === 'split' && (
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
              <MarkdownRenderer
                content={editContent}
                projectSlug={projectSlug}
                entityMentions={documentEntities}
              />
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
            {mediaKind === 'pdf' ? (
              <div className="space-y-4">
                <PdfDocument
                  file={assetUrl}
                  onLoadSuccess={({ numPages }) => setPdfPageCount(numPages)}
                  onLoadError={(error) => console.error('PDF render failed', error)}
                >
                  {Array.from({ length: pdfPageCount || 1 }, (_value, index) => (
                    <div key={`page-${index + 1}`} className="overflow-auto rounded border border-border bg-muted p-3">
                      <PdfPage pageNumber={index + 1} width={900} renderTextLayer renderAnnotationLayer />
                    </div>
                  ))}
                </PdfDocument>
              </div>
            ) : mediaKind === 'image' ? (
              <div className="overflow-hidden rounded border border-border bg-muted p-4">
                <img src={assetUrl} alt={metadata.title} className="max-h-[70vh] w-full object-contain" />
              </div>
            ) : language === 'markdown' ? (
              <MarkdownRenderer
                content={document.content}
                projectSlug={projectSlug}
                entityMentions={documentEntities}
              />
            ) : (
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
                {document.content}
              </pre>
            )}
          </CardShell>
          {showSearchSource && sourceContext && (
            <SearchSourceCard
              query={sourceContext.query}
              queryLabel={sourceContext.queryLabel}
              snippet={sourceContext.snippet}
              heading={sourceContext.heading}
              signals={sourceContext.signals}
              versionNumber={sourceContext.versionNumber}
              startChar={sourceContext.startChar}
              endChar={sourceContext.endChar}
              chunkId={sourceContext.chunkId}
            />
          )}
        </div>
      )}

      {viewMode === 'raw' && (
        <div className={showSearchSource ? 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]' : ''}>
          <CardShell title="Raw document">
            {mediaKind === 'text' ? (
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-sm">
                {document.content}
              </pre>
            ) : (
              <div className="space-y-3 text-sm">
                <div className="rounded border border-border bg-muted p-4">
                  <div><span className="font-medium">Asset:</span> {metadata.relative_path}</div>
                  <div><span className="font-medium">MIME type:</span> {document.mime_type ?? 'unknown'}</div>
                  <div><span className="font-medium">Version:</span> v{metadata.version}</div>
                </div>
                <a
                  href={assetUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-9 items-center rounded border border-border bg-white px-3 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Open asset
                </a>
              </div>
            )}
          </CardShell>
          {showSearchSource && sourceContext && (
            <SearchSourceCard
              query={sourceContext.query}
              queryLabel={sourceContext.queryLabel}
              snippet={sourceContext.snippet}
              heading={sourceContext.heading}
              signals={sourceContext.signals}
              versionNumber={sourceContext.versionNumber}
              startChar={sourceContext.startChar}
              endChar={sourceContext.endChar}
              chunkId={sourceContext.chunkId}
            />
          )}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
        <CardShell title="Annotations">
          <div className="space-y-4">
            {!document.metadata.version_id && (
              <div className="rounded border border-border bg-muted px-3 py-3 text-sm text-muted-foreground">
                Version-aware annotations become available after the document has been synced into the operational database.
              </div>
            )}
            {document.metadata.version_id && (
              <div className="grid gap-3 md:grid-cols-[10rem_minmax(0,1fr)]">
                <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Type
                  <select
                    value={annotationType}
                    onChange={(event) =>
                      setAnnotationType(event.target.value as 'comment' | 'highlight' | 'pin')
                    }
                    className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  >
                    <option value="comment">Comment</option>
                    <option value="highlight">Highlight</option>
                    <option value="pin">Pin</option>
                  </select>
                </label>
                <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Note
                  <Textarea
                    value={annotationContent}
                    onChange={(event) => setAnnotationContent(event.target.value)}
                    placeholder="Capture a comment, pin rationale, or highlight context."
                    className="min-h-24"
                  />
                </label>
              </div>
            )}
            {document.metadata.version_id && (
              <div className="grid gap-3 md:grid-cols-3">
                <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Start char
                  <Input
                    value={annotationStart}
                    onChange={(event) => setAnnotationStart(event.target.value)}
                    inputMode="numeric"
                    placeholder="optional"
                  />
                </label>
                <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  End char
                  <Input
                    value={annotationEnd}
                    onChange={(event) => setAnnotationEnd(event.target.value)}
                    inputMode="numeric"
                    placeholder="optional"
                  />
                </label>
                <div className="flex items-end">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleCreateAnnotation}
                    disabled={createAnnotationMutation.isPending || !document.metadata.version_id}
                  >
                    {createAnnotationMutation.isPending ? 'Saving…' : 'Add annotation'}
                  </Button>
                </div>
              </div>
            )}
            <div className="space-y-3">
              {annotations.length === 0 ? (
                <div className="rounded border border-dashed border-border bg-muted px-3 py-4 text-sm text-muted-foreground">
                  No annotations yet for this version.
                </div>
              ) : (
                annotations.map((annotation: AnnotationItem) => (
                  <div
                    key={annotation.id}
                    className="rounded border border-border bg-white px-4 py-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{annotation.annotation_type}</Badge>
                        {annotation.start_char != null && annotation.end_char != null && (
                          <Badge variant="outline">
                            {annotation.start_char}-{annotation.end_char}
                          </Badge>
                        )}
                        {annotation.created_at && (
                          <span className="text-xs text-muted-foreground">
                            {new Date(annotation.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                      <Button
                        type="button"
                        size="xs"
                        variant="outline"
                        onClick={() => void deleteAnnotationMutation.mutateAsync(annotation.id)}
                      >
                        <Trash2 className="size-3.5" />
                        Remove
                      </Button>
                    </div>
                    {annotation.content && (
                      <p className="mt-3 text-sm leading-6 text-foreground">{annotation.content}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </CardShell>

        <CardShell title="Collections">
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
              <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Add to existing collection
                <select
                  value={selectedCollectionId}
                  onChange={(event) => setSelectedCollectionId(event.target.value)}
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <option value="">Choose collection</option>
                  {collections.map((collection: CollectionItem) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end">
                <Button
                  type="button"
                  size="sm"
                  onClick={handleAddToCollection}
                  disabled={addToCollectionMutation.isPending || !selectedCollectionId}
                >
                  {addToCollectionMutation.isPending ? 'Adding…' : 'Add'}
                </Button>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
              <label className="space-y-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                Create collection
                <Input
                  value={newCollectionName}
                  onChange={(event) => setNewCollectionName(event.target.value)}
                  placeholder="Architecture decisions"
                />
              </label>
              <div className="flex items-end">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleCreateCollection}
                  disabled={createCollectionMutation.isPending || !newCollectionName.trim()}
                >
                  <FolderPlus className="size-3.5" />
                  {createCollectionMutation.isPending ? 'Creating…' : 'Create + add'}
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              {documentCollections.length === 0 ? (
                <div className="rounded border border-dashed border-border bg-muted px-3 py-4 text-sm text-muted-foreground">
                  This document is not in any collection yet.
                </div>
              ) : (
                documentCollections.map((collection: CollectionItem) => (
                  <div
                    key={collection.id}
                    className="flex items-center justify-between gap-3 rounded border border-border bg-white px-4 py-3"
                  >
                    <div>
                      <div className="font-medium">{collection.name}</div>
                      {collection.description && (
                        <div className="mt-1 text-sm text-muted-foreground">{collection.description}</div>
                      )}
                    </div>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => void removeFromCollectionMutation.mutateAsync(collection.id)}
                    >
                      <Trash2 className="size-3.5" />
                      Remove
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>
        </CardShell>
      </div>

      {headings.length > 0 && (
        <div className="rounded border border-border bg-white p-5 shadow-sm">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Outline
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {headings.map((heading) => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                className="rounded border border-border bg-muted px-3 py-2 text-sm transition-colors hover:bg-accent/50"
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
  queryLabel,
  snippet,
  heading,
  signals,
  versionNumber,
  startChar,
  endChar,
  chunkId,
}: {
  query?: string
  queryLabel?: string
  snippet?: string
  heading?: string
  signals: string[]
  versionNumber?: number
  startChar?: number
  endChar?: number
  chunkId?: string
}) {
  return (
    <CardShell title="Source evidence">
      <div className="space-y-4 text-sm">
        {query && (
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              {queryLabel ?? 'Query'}
            </div>
            <div className="mt-2 rounded border border-border bg-muted px-3 py-2 font-mono text-xs">
              {query}
            </div>
          </div>
        )}
        {heading && (
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Heading
            </div>
            <div className="mt-2 text-sm text-foreground">{heading}</div>
          </div>
        )}
        {(versionNumber != null || startChar != null || endChar != null || chunkId) && (
          <div className="grid gap-3 md:grid-cols-3">
            {versionNumber != null && (
              <div className="rounded border border-border bg-muted px-3 py-3">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Version
                </div>
                <div className="mt-2 text-sm text-foreground">v{versionNumber}</div>
              </div>
            )}
            {(startChar != null || endChar != null) && (
              <div className="rounded border border-border bg-muted px-3 py-3">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Characters
                </div>
                <div className="mt-2 text-sm text-foreground">
                  {startChar ?? '?'}-{endChar ?? '?'}
                </div>
              </div>
            )}
            {chunkId && (
              <div className="rounded border border-border bg-muted px-3 py-3">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Chunk
                </div>
                <div className="mt-2 break-all font-mono text-xs text-foreground">
                  {chunkId}
                </div>
              </div>
            )}
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
        {snippet && (
          <div className="rounded border border-border bg-muted px-4 py-4 leading-6 text-foreground">
            {snippet}
          </div>
        )}
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
    <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-[32px] py-[28px]">
      {title && (
        <div className="mb-4 text-[9px] font-semibold text-[#666]">
          {title.toUpperCase()}
        </div>
      )}
      {children}
    </div>
  )
}
