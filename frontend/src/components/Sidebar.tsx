import { useEffect, useMemo, useState, type ChangeEvent, type CSSProperties } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import {
  BookOpen,
  Copy,
  FileText,
  Files,
  FolderPlus,
  Inbox,
  LayoutGrid,
  MoveRight,
  Network,
  Plus,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type AttachmentItem, type DocumentMeta, type GeneratedFile } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectsQuery, useProjectWorkspaceQuery } from '@/lib/workspace-query'
import { CreateDocumentDialog, openTemplateDialog } from './CreateDocumentDialog'
import { CreateProjectDialog } from './CreateProjectDialog'

const EMPTY_DOCUMENTS: DocumentMeta[] = []
const EMPTY_ATTACHMENTS: AttachmentItem[] = []
const EMPTY_GENERATED_FILES: GeneratedFile[] = []

interface SidebarProps {
  style?: CSSProperties
}

export function Sidebar({ style }: SidebarProps) {
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

  // Build folder tree from document paths
  const folderTree = useMemo(() => {
    const folders = new Set<string>()
    for (const doc of docs) {
      const parts = doc.relative_path.split('/')
      for (let i = 1; i < parts.length; i++) {
        folders.add(parts.slice(0, i).join('/'))
      }
    }
    return [...folders].sort()
  }, [docs])

  const isActiveNav = (path: string) => {
    if (path === '/' && selectedProject) {
      return location.pathname === `/projects/${selectedProject}`
    }
    return location.pathname === path || location.pathname.startsWith(path + '/')
  }

  const dashboardPath = selectedProject ? `/projects/${selectedProject}` : '/'

  return (
    <aside className="flex shrink-0 flex-col bg-sidebar text-sidebar-foreground" style={style}>
      <ScrollArea className="flex-1">
        {/* Nav links — Figma: text only, blue left border on active, 13px, py-[10px] px-[16px] */}
        <div className="flex flex-col gap-[2px] py-4">
          <Link
            to={selectedProject ? '/projects/$slug' : '/'}
            params={selectedProject ? { slug: selectedProject } : undefined}
            className={`flex items-center py-[10px] pl-3 pr-4 text-[13px] ${
              isActiveNav(dashboardPath)
                ? 'border-l-4 border-primary bg-sidebar-accent text-white'
                : 'border-l-4 border-transparent text-[#999] hover:text-white'
            }`}
          >
            Dashboard
          </Link>
          <Link
            to="/search"
            className={`flex items-center py-[10px] pl-3 pr-4 text-[13px] ${
              isActiveNav('/search')
                ? 'border-l-4 border-primary bg-sidebar-accent text-white'
                : 'border-l-4 border-transparent text-[#999] hover:text-white'
            }`}
          >
            Search
          </Link>
          {selectedProject && (
            <>
              <Link
                to="/projects/$slug/inbox"
                params={{ slug: selectedProject }}
                className={`flex items-center py-[10px] pl-3 pr-4 text-[13px] ${
                  isActiveNav(`/projects/${selectedProject}/inbox`) || isActiveNav(`/projects/${selectedProject}/review`)
                    ? 'border-l-4 border-primary bg-sidebar-accent text-white'
                    : 'border-l-4 border-transparent text-[#999] hover:text-white'
                }`}
              >
                Inbox
              </Link>
              <Link
                to="/projects/$slug/sessions"
                params={{ slug: selectedProject }}
                className={`flex items-center py-[10px] pl-3 pr-4 text-[13px] ${
                  isActiveNav(`/projects/${selectedProject}/sessions`)
                    ? 'border-l-4 border-primary bg-sidebar-accent text-white'
                    : 'border-l-4 border-transparent text-[#999] hover:text-white'
                }`}
              >
                Sessions
              </Link>
            </>
          )}
        </div>

        {/* Separator */}
        <div className="h-px w-full bg-white/10" />

        {/* Quick Actions — Figma: 9px semibold #666 label, 11px medium #22A5F1 text */}
        {selectedProject && (
          <div className="py-2">
            <div className="pb-1 pl-4 pt-2 text-[9px] font-semibold text-[#666]">
              QUICK ACTIONS
            </div>
            <CreateDocumentDialog
              projectSlug={selectedProject}
              onCreated={() => refreshProjectState().catch(console.error)}
            />
            <button
              type="button"
              className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-primary hover:text-primary/80"
              onClick={() => {
                const input = document.createElement('input')
                input.type = 'file'
                input.onchange = (event) => {
                  handleUploadFile(event as unknown as ChangeEvent<HTMLInputElement>)
                }
                input.click()
              }}
            >
              + Upload File
            </button>
            <button
              type="button"
              className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-primary hover:text-primary/80"
              onClick={() => openTemplateDialog('session-note')}
            >
              + New Session
            </button>
            <button
              type="button"
              className="w-full py-[5px] pl-4 pr-3 text-left text-[11px] font-medium text-primary hover:text-primary/80"
              onClick={() => openTemplateDialog('adr')}
            >
              + New ADR
            </button>
          </div>
        )}

        {/* Separator */}
        <div className="h-px w-full bg-white/10" />

        {/* File Cabinet — Figma: indented folder tree, 11px #999 text */}
        {selectedProject && (
          <div className="py-2">
            <div className="pb-1 pl-4 pt-2 text-[9px] font-semibold text-[#666]">
              FILE CABINET
            </div>
            <div className="mt-1">
              {folderTree.map((folder) => {
                const depth = folder.split('/').length - 1
                return (
                  <div
                    key={folder}
                    className="py-[3px] pr-3 text-[11px] text-[#999]"
                    style={{ paddingLeft: `${16 + depth * 12}px` }}
                  >
                    ▸ {folder.split('/').pop()}/
                  </div>
                )
              })}
              {docs.map((document) => {
                const parts = document.relative_path.split('/')
                const depth = parts.length - 1
                const filename = parts[parts.length - 1]
                return (
                  <Link
                    key={document.relative_path}
                    to="/projects/$slug/docs/$"
                    params={{ slug: selectedProject, _splat: document.relative_path }}
                    className={`block py-[3px] pr-3 text-[11px] transition-colors ${
                      selectedDocument === document.relative_path
                        ? 'bg-sidebar-accent text-white'
                        : 'text-[#999] hover:text-white'
                    }`}
                    style={{ paddingLeft: `${16 + depth * 12}px` }}
                  >
                    {filename}
                  </Link>
                )
              })}
            </div>

            {/* Attachments folder */}
            {attachments.length > 0 && (
              <div className="py-[3px] pl-4 pr-3 text-[11px] text-[#999]">
                ▸ attachments/
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
