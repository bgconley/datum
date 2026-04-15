import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import {
  Copy,
  Files,
  FolderPlus,
  LayoutGrid,
  MoveRight,
  Network,
  Search,
  ShieldAlert,
  Trash2,
  Upload,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type AttachmentItem, type DocumentMeta, type GeneratedFile } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectsQuery, useProjectWorkspaceQuery } from '@/lib/workspace-query'
import { CreateDocumentDialog } from './CreateDocumentDialog'
import { CreateProjectDialog } from './CreateProjectDialog'

const EMPTY_DOCUMENTS: DocumentMeta[] = []
const EMPTY_ATTACHMENTS: AttachmentItem[] = []
const EMPTY_GENERATED_FILES: GeneratedFile[] = []

export function Sidebar() {
  const [showGenerated, setShowGenerated] = useState(false)
  const [folderPath, setFolderPath] = useState('docs')
  const [folderActionPath, setFolderActionPath] = useState('docs')
  const [folderRenamePath, setFolderRenamePath] = useState('docs-renamed')
  const [movePath, setMovePath] = useState('')
  const [selectedAttachmentPath, setSelectedAttachmentPath] = useState<string | null>(null)
  const [attachmentMovePath, setAttachmentMovePath] = useState('')
  const [moving, setMoving] = useState(false)
  const [movingAttachment, setMovingAttachment] = useState(false)
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [renamingFolder, setRenamingFolder] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deletingFolder, setDeletingFolder] = useState(false)
  const [deletingAttachment, setDeletingAttachment] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [operationError, setOperationError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()

  const selectedProject = location.pathname.startsWith('/projects/')
    ? decodeURIComponent(location.pathname.split('/')[2] ?? '')
    : null
  const documentPrefix = selectedProject ? `/projects/${selectedProject}/docs/` : null
  let selectedDocument: string | null = null
  if (documentPrefix && location.pathname.startsWith(documentPrefix)) {
    selectedDocument = decodeURIComponent(location.pathname.slice(documentPrefix.length))
    if (selectedDocument.endsWith('/history')) {
      selectedDocument = selectedDocument.slice(0, -'/history'.length)
    }
  }

  const projectsQuery = useProjectsQuery()
  const workspaceQuery = useProjectWorkspaceQuery(selectedProject, { subscribe: true })
  const projects = projectsQuery.data ?? []
  const project = workspaceQuery.data?.project ?? null
  const docs = workspaceQuery.data?.documents ?? EMPTY_DOCUMENTS
  const attachments = workspaceQuery.data?.attachments ?? EMPTY_ATTACHMENTS
  const generatedFiles = workspaceQuery.data?.generated_files ?? EMPTY_GENERATED_FILES
  const intelligenceQuery = useQuery({
    queryKey: selectedProject ? queryKeys.intelligenceSummary(selectedProject) : ['projects', 'intelligence', 'idle'],
    queryFn: () => api.intelligence.summary(selectedProject!),
    enabled: Boolean(selectedProject),
  })
  const pendingCandidateCount = intelligenceQuery.data?.pending_candidate_count ?? 0

  const selectedDocMeta = useMemo(
    () => docs.find((document) => document.relative_path === selectedDocument) ?? null,
    [docs, selectedDocument],
  )
  const absoluteDocumentPath =
    project?.filesystem_path && selectedDocument
      ? `${project.filesystem_path}/${selectedDocument}`
      : null
  const selectedAttachmentMeta = useMemo(
    () => attachments.find((attachment) => attachment.relative_path === selectedAttachmentPath) ?? null,
    [attachments, selectedAttachmentPath],
  )
  const absoluteAttachmentPath =
    project?.filesystem_path && selectedAttachmentMeta
      ? `${project.filesystem_path}/${selectedAttachmentMeta.relative_path}`
      : null

  useEffect(() => {
    setMovePath(selectedDocument ?? '')
  }, [selectedDocument])

  useEffect(() => {
    if (!selectedDocument) {
      return
    }
    const lastSlash = selectedDocument.lastIndexOf('/')
    const parentFolder = lastSlash >= 0 ? selectedDocument.slice(0, lastSlash) : 'docs'
    setFolderActionPath(parentFolder || 'docs')
    setFolderRenamePath(parentFolder ? `${parentFolder}-renamed` : 'docs-renamed')
  }, [selectedDocument])

  useEffect(() => {
    if (attachments.length === 0) {
      setSelectedAttachmentPath(null)
      return
    }
    if (!selectedAttachmentPath || !attachments.some((attachment) => attachment.relative_path === selectedAttachmentPath)) {
      setSelectedAttachmentPath(attachments[0]?.relative_path ?? null)
    }
  }, [attachments, selectedAttachmentPath])

  useEffect(() => {
    setAttachmentMovePath(selectedAttachmentPath ?? '')
  }, [selectedAttachmentPath])

  const refreshProjectState = async () => {
    if (!selectedProject) {
      return
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.workspace(selectedProject) })
  }

  const copyText = async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(key)
      window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 1400)
    } catch (error) {
      console.error(error)
    }
  }

  const handleCreateFolder = async () => {
    if (!selectedProject || !folderPath.trim()) {
      return
    }
    setCreatingFolder(true)
    setOperationError(null)
    try {
      await api.filesystem.mkdir(selectedProject, { path: folderPath.trim() })
      await refreshProjectState()
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleRenameFolder = async () => {
    if (!selectedProject || !folderActionPath.trim() || !folderRenamePath.trim()) {
      return
    }
    setRenamingFolder(true)
    setOperationError(null)
    try {
      await api.documents.renameFolder(selectedProject, {
        relative_path: folderActionPath.trim(),
        new_relative_path: folderRenamePath.trim(),
      })
      await refreshProjectState()
      if (selectedDocument?.startsWith(`${folderActionPath.trim()}/`)) {
        const nextPath = selectedDocument.replace(folderActionPath.trim(), folderRenamePath.trim())
        navigate({
          to: '/projects/$slug/docs/$',
          params: { slug: selectedProject, _splat: nextPath },
        })
      }
      setFolderActionPath(folderRenamePath.trim())
      setFolderRenamePath(`${folderRenamePath.trim()}-renamed`)
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setRenamingFolder(false)
    }
  }

  const handleDeleteFolder = async () => {
    if (!selectedProject || !folderActionPath.trim()) {
      return
    }
    if (!window.confirm(`Delete folder ${folderActionPath.trim()} and archive its documents?`)) {
      return
    }
    setDeletingFolder(true)
    setOperationError(null)
    try {
      await api.documents.deleteFolder(selectedProject, folderActionPath.trim())
      await refreshProjectState()
      if (selectedDocument?.startsWith(`${folderActionPath.trim()}/`)) {
        navigate({ to: '/projects/$slug', params: { slug: selectedProject } })
      }
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setDeletingFolder(false)
    }
  }

  const handleMoveDocument = async () => {
    if (!selectedProject || !selectedDocument || !movePath.trim()) {
      return
    }
    setMoving(true)
    setOperationError(null)
    try {
      const moved = await api.filesystem.rename(selectedProject, {
        old_path: selectedDocument,
        new_path: movePath.trim(),
      })
      await refreshProjectState()
      navigate({
        to: '/projects/$slug/docs/$',
        params: { slug: selectedProject, _splat: moved.new_path },
      })
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setMoving(false)
    }
  }

  const handleDeleteDocument = async () => {
    if (!selectedProject || !selectedDocument) {
      return
    }
    if (!window.confirm(`Delete ${selectedDocument}?`)) {
      return
    }
    setDeleting(true)
    setOperationError(null)
    try {
      await api.filesystem.delete(selectedProject, selectedDocument)
      await refreshProjectState()
      navigate({ to: '/projects/$slug', params: { slug: selectedProject } })
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setDeleting(false)
    }
  }

  const handleMoveAttachment = async () => {
    if (!selectedProject || !selectedAttachmentMeta || !attachmentMovePath.trim()) {
      return
    }
    setMovingAttachment(true)
    setOperationError(null)
    try {
      const moved = await api.attachments.move(selectedProject, selectedAttachmentMeta.relative_path, {
        new_relative_path: attachmentMovePath.trim(),
      })
      await refreshProjectState()
      setSelectedAttachmentPath(moved.relative_path)
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setMovingAttachment(false)
    }
  }

  const handleDeleteAttachment = async () => {
    if (!selectedProject || !selectedAttachmentMeta) {
      return
    }
    if (!window.confirm(`Delete attachment ${selectedAttachmentMeta.filename}? Blob bytes will be retained.`)) {
      return
    }
    setDeletingAttachment(true)
    setOperationError(null)
    try {
      await api.attachments.delete(selectedProject, selectedAttachmentMeta.relative_path)
      await refreshProjectState()
      setSelectedAttachmentPath(null)
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setDeletingAttachment(false)
    }
  }

  const handleUploadFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !selectedProject) {
      return
    }
    setUploading(true)
    setOperationError(null)
    try {
      await api.upload.file(selectedProject, file)
      await refreshProjectState()
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : String(error))
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  return (
    <aside className="flex w-[20rem] shrink-0 flex-col border-r border-border/80 bg-[linear-gradient(180deg,rgba(15,23,42,0.95),rgba(9,14,24,0.88))]">
      <div className="border-b border-border/80 px-4 py-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Datum
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Project cabinet</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Filesystem-first memory with document routes, project dashboards, and generated-state visibility.
        </p>
      </div>
      <ScrollArea className="flex-1">
        <div className="border-b border-border/80 p-3">
          <Link
            to="/search"
            className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
              location.pathname === '/search' ? 'bg-foreground text-background' : 'hover:bg-accent'
            }`}
          >
            <Search className="size-4" />
            <span>Search</span>
            <kbd className="ml-auto rounded border px-1.5 py-0.5 text-[10px] text-current/70">
              /
            </kbd>
          </Link>
        </div>

        <div className="p-3">
          <h2 className="px-1 py-1 text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Projects
          </h2>
          <div className="mt-2 space-y-1">
            {projects.map((item) => (
              <Link
                key={item.slug}
                to="/projects/$slug"
                params={{ slug: item.slug }}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                  selectedProject === item.slug ? 'bg-accent text-foreground' : 'hover:bg-accent/70'
                }`}
              >
                <LayoutGrid className="size-4 text-muted-foreground" />
                <span className="truncate">{item.name}</span>
              </Link>
            ))}
          </div>
          <div className="mt-3">
            <CreateProjectDialog
              onCreated={() =>
                queryClient.invalidateQueries({ queryKey: queryKeys.projects }).catch(console.error)
              }
            />
          </div>
        </div>

        {selectedProject && (
          <div className="border-t border-border/80 p-3">
            <div className="flex items-center justify-between gap-2 px-1">
              <h2 className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
                Documents
              </h2>
              <span className="text-xs text-muted-foreground">{docs.length}</span>
            </div>

            <Link
              to="/projects/$slug"
              params={{ slug: selectedProject }}
              className={`mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                location.pathname === `/projects/${selectedProject}`
                  ? 'bg-accent text-foreground'
                  : 'hover:bg-accent/70'
              }`}
            >
              <LayoutGrid className="size-4 text-muted-foreground" />
              Dashboard
            </Link>

            <Link
              to="/projects/$slug/inbox"
              params={{ slug: selectedProject }}
              className={`mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                location.pathname === `/projects/${selectedProject}/inbox` ||
                location.pathname === `/projects/${selectedProject}/review`
                  ? 'bg-accent text-foreground'
                  : 'hover:bg-accent/70'
              }`}
            >
              <ShieldAlert className="size-4 text-muted-foreground" />
              Review inbox
              {pendingCandidateCount > 0 && (
                <span className="ml-auto rounded-full border border-border/70 bg-background/70 px-2 py-0.5 text-[11px]">
                  {pendingCandidateCount}
                </span>
              )}
            </Link>

            <Link
              to="/projects/$slug/entities"
              params={{ slug: selectedProject }}
              className={`mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                location.pathname === `/projects/${selectedProject}/entities` ||
                location.pathname.startsWith(`/projects/${selectedProject}/entities/`)
                  ? 'bg-accent text-foreground'
                  : 'hover:bg-accent/70'
              }`}
            >
              <Network className="size-4 text-muted-foreground" />
              Entity graph
            </Link>

            <div className="mt-2 space-y-1">
              {docs.map((document) => (
                <Link
                  key={document.relative_path}
                  to="/projects/$slug/docs/$"
                  params={{ slug: selectedProject, _splat: document.relative_path }}
                  className={`block rounded-xl px-3 py-2 text-sm transition-colors ${
                    selectedDocument === document.relative_path
                      ? 'bg-foreground text-background'
                      : 'hover:bg-accent/70'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">{document.title}</div>
                    <div className="mt-1 truncate text-xs text-current/70">{document.relative_path}</div>
                  </div>
                </Link>
              ))}
            </div>

            <div className="mt-3">
              <CreateDocumentDialog
                projectSlug={selectedProject}
                onCreated={() => refreshProjectState().catch(console.error)}
              />
            </div>

            {operationError && (
              <div className="mt-3 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {operationError}
              </div>
            )}

            <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                <FolderPlus className="size-3.5" />
                Create folder
              </div>
              <div className="mt-3 flex gap-2">
                <Input
                  value={folderPath}
                  onChange={(event) => setFolderPath(event.target.value)}
                  className="text-xs font-mono"
                />
                <Button size="sm" variant="outline" onClick={handleCreateFolder} disabled={creatingFolder}>
                  {creatingFolder ? 'Creating…' : 'Create'}
                </Button>
              </div>
            </div>

            <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                Folder actions
              </div>
              <div className="mt-3 space-y-2">
                <Input
                  value={folderActionPath}
                  onChange={(event) => setFolderActionPath(event.target.value)}
                  className="text-xs font-mono"
                  placeholder="docs/specs"
                />
                <Input
                  value={folderRenamePath}
                  onChange={(event) => setFolderRenamePath(event.target.value)}
                  className="text-xs font-mono"
                  placeholder="docs/specs-renamed"
                />
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleRenameFolder} disabled={renamingFolder}>
                    <MoveRight className="size-3.5" />
                    {renamingFolder ? 'Renaming…' : 'Rename'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-red-500/30 text-red-100 hover:bg-red-500/10"
                    onClick={handleDeleteFolder}
                    disabled={deletingFolder}
                  >
                    <Trash2 className="size-3.5" />
                    {deletingFolder ? 'Deleting…' : 'Delete'}
                  </Button>
                </div>
              </div>
            </div>

            <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                <Upload className="size-3.5" />
                Upload attachment
              </div>
              <label className="mt-3 flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-border/70 bg-background/60 px-3 py-4 text-xs text-muted-foreground transition-colors hover:bg-accent/40">
                <input type="file" className="hidden" onChange={handleUploadFile} disabled={uploading} />
                {uploading ? 'Uploading…' : 'Choose file'}
              </label>
            </div>

            <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Attachments
                </div>
                <span className="text-xs text-muted-foreground">{attachments.length}</span>
              </div>
              <div className="mt-3 space-y-2">
                {attachments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No attachments uploaded yet.</div>
                ) : (
                  attachments.map((attachment) => (
                    <button
                      key={attachment.relative_path}
                      type="button"
                      className={`block w-full rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                        selectedAttachmentMeta?.relative_path === attachment.relative_path
                          ? 'bg-foreground text-background'
                          : 'hover:bg-accent/70'
                      }`}
                      onClick={() => setSelectedAttachmentPath(attachment.relative_path)}
                    >
                      <div className="truncate font-medium">{attachment.filename}</div>
                      <div className="mt-1 truncate text-xs text-current/70">{attachment.relative_path}</div>
                    </button>
                  ))
                )}
              </div>
            </div>

            {selectedAttachmentMeta && (
              <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Attachment actions
                </div>
                <div className="mt-3 space-y-3">
                  <div className="rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-xs">
                    <div className="font-medium text-foreground">{selectedAttachmentMeta.filename}</div>
                    <div className="mt-1 font-mono text-muted-foreground">
                      {selectedAttachmentMeta.relative_path}
                    </div>
                    <div className="mt-2 text-muted-foreground">
                      {selectedAttachmentMeta.byte_size} bytes · {selectedAttachmentMeta.content_type}
                    </div>
                    {absoluteAttachmentPath && (
                      <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                        {absoluteAttachmentPath}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => copyText(selectedAttachmentMeta.relative_path, 'attachment-relative')}
                    >
                      <Copy className="size-3" />
                      {copied === 'attachment-relative' ? 'Copied path' : 'Copy relative path'}
                    </Button>
                    {absoluteAttachmentPath && (
                      <Button
                        type="button"
                        size="xs"
                        variant="outline"
                        onClick={() => copyText(absoluteAttachmentPath, 'attachment-absolute')}
                      >
                        <Files className="size-3" />
                        {copied === 'attachment-absolute' ? 'Copied absolute path' : 'Copy absolute path'}
                      </Button>
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                      Rename / move
                    </div>
                    <div className="flex gap-2">
                      <Input
                        value={attachmentMovePath}
                        onChange={(event) => setAttachmentMovePath(event.target.value)}
                        className="text-xs font-mono"
                      />
                      <Button size="sm" variant="outline" onClick={handleMoveAttachment} disabled={movingAttachment}>
                        <MoveRight className="size-3.5" />
                        {movingAttachment ? 'Moving…' : 'Move'}
                      </Button>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-red-500/30 text-red-100 hover:bg-red-500/10"
                    onClick={handleDeleteAttachment}
                    disabled={deletingAttachment}
                  >
                    <Trash2 className="size-3.5" />
                    {deletingAttachment ? 'Deleting…' : 'Delete'}
                  </Button>
                </div>
              </div>
            )}

            {selectedDocMeta && (
              <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Document actions
                </div>
                <div className="mt-3 space-y-3">
                  <div className="rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-xs">
                    <div className="font-medium text-foreground">{selectedDocMeta.title}</div>
                    <div className="mt-1 font-mono text-muted-foreground">{selectedDocMeta.relative_path}</div>
                    {absoluteDocumentPath && (
                      <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                        {absoluteDocumentPath}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      onClick={() => copyText(selectedDocMeta.relative_path, 'relative')}
                    >
                      <Copy className="size-3" />
                      {copied === 'relative' ? 'Copied path' : 'Copy relative path'}
                    </Button>
                    {absoluteDocumentPath && (
                      <Button
                        type="button"
                        size="xs"
                        variant="outline"
                        onClick={() => copyText(absoluteDocumentPath, 'absolute')}
                      >
                        <Files className="size-3" />
                        {copied === 'absolute' ? 'Copied absolute path' : 'Copy absolute path'}
                      </Button>
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                      Rename / move
                    </div>
                    <div className="flex gap-2">
                      <Input
                        value={movePath}
                        onChange={(event) => setMovePath(event.target.value)}
                        className="text-xs font-mono"
                      />
                      <Button size="sm" variant="outline" onClick={handleMoveDocument} disabled={moving}>
                        <MoveRight className="size-3.5" />
                        {moving ? 'Moving…' : 'Move'}
                      </Button>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-red-500/30 text-red-100 hover:bg-red-500/10"
                    onClick={handleDeleteDocument}
                    disabled={deleting}
                  >
                    <Trash2 className="size-3.5" />
                    {deleting ? 'Deleting…' : 'Delete'}
                  </Button>
                </div>
              </div>
            )}

            <div className="mt-3 rounded-2xl border border-border/80 bg-card/70 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                  Generated files
                </div>
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  onClick={() => setShowGenerated((current) => !current)}
                >
                  {showGenerated ? 'Hide .piq/' : 'Show .piq/'}
                </Button>
              </div>
              {showGenerated && (
                <div className="mt-3 space-y-2">
                  {generatedFiles.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No generated files yet.</div>
                  ) : (
                    generatedFiles.map((file) => (
                      <div
                        key={file.relative_path}
                        className="rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-xs"
                      >
                        <div className="truncate font-mono">{file.relative_path}</div>
                        <div className="mt-1 text-muted-foreground">{file.size_bytes} bytes</div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
