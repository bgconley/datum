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
import { api, type DocumentMeta, type GeneratedFile } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectsQuery, useProjectWorkspaceQuery } from '@/lib/workspace-query'
import { CreateDocumentDialog } from './CreateDocumentDialog'
import { CreateProjectDialog } from './CreateProjectDialog'

const EMPTY_DOCUMENTS: DocumentMeta[] = []
const EMPTY_GENERATED_FILES: GeneratedFile[] = []

export function Sidebar() {
  const [showGenerated, setShowGenerated] = useState(false)
  const [folderPath, setFolderPath] = useState('docs')
  const [movePath, setMovePath] = useState('')
  const [moving, setMoving] = useState(false)
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
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

  useEffect(() => {
    setMovePath(selectedDocument ?? '')
  }, [selectedDocument])

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
    try {
      await api.filesystem.mkdir(selectedProject, { path: folderPath.trim() })
      await refreshProjectState()
    } catch (error) {
      alert(String(error))
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleMoveDocument = async () => {
    if (!selectedProject || !selectedDocument || !movePath.trim()) {
      return
    }
    setMoving(true)
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
      alert(String(error))
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
    try {
      await api.filesystem.delete(selectedProject, selectedDocument)
      await refreshProjectState()
      navigate({ to: '/projects/$slug', params: { slug: selectedProject } })
    } catch (error) {
      alert(String(error))
    } finally {
      setDeleting(false)
    }
  }

  const handleUploadFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !selectedProject) {
      return
    }
    setUploading(true)
    try {
      await api.upload.file(selectedProject, file)
      await refreshProjectState()
    } catch (error) {
      alert(String(error))
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
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                <Upload className="size-3.5" />
                Upload attachment
              </div>
              <label className="mt-3 flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-border/70 bg-background/60 px-3 py-4 text-xs text-muted-foreground transition-colors hover:bg-accent/40">
                <input type="file" className="hidden" onChange={handleUploadFile} disabled={uploading} />
                {uploading ? 'Uploading…' : 'Choose file'}
              </label>
            </div>

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
