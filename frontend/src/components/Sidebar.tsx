import { useEffect, useState } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import { FileText, LayoutGrid, Search } from 'lucide-react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Project, type DocumentMeta } from '@/lib/api'
import { CreateProjectDialog } from './CreateProjectDialog'
import { CreateDocumentDialog } from './CreateDocumentDialog'

export function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([])
  const [docs, setDocs] = useState<DocumentMeta[]>([])
  const location = useLocation()

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

  useEffect(() => {
    api.projects.list().then(setProjects).catch(console.error)
  }, [])

  useEffect(() => {
    if (!selectedProject) {
      setDocs([])
      return
    }
    api.documents.list(selectedProject).then(setDocs).catch(console.error)
  }, [selectedProject])

  return (
    <aside className="flex w-[18rem] shrink-0 flex-col border-r border-border/80 bg-[linear-gradient(180deg,rgba(249,250,251,0.96),rgba(244,244,245,0.86))]">
      <div className="border-b border-border/80 px-4 py-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
          Datum
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Project cabinet</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Dashboards, documents, and search anchored to the filesystem-first cabinet.
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
            {projects.map((project) => (
              <Link
                key={project.slug}
                to="/projects/$slug"
                params={{ slug: project.slug }}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                  selectedProject === project.slug ? 'bg-accent text-foreground' : 'hover:bg-accent/70'
                }`}
              >
                <LayoutGrid className="size-4 text-muted-foreground" />
                <span className="truncate">{project.name}</span>
              </Link>
            ))}
          </div>
          <div className="mt-3">
            <CreateProjectDialog onCreated={() => api.projects.list().then(setProjects).catch(console.error)} />
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
                  <div className="flex items-start gap-2">
                    <FileText className="mt-0.5 size-4 shrink-0 text-current/70" />
                    <div className="min-w-0">
                      <div className="truncate font-medium">{document.title}</div>
                      <div className="truncate text-xs text-current/70">
                        {document.relative_path}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-3">
              <CreateDocumentDialog
                projectSlug={selectedProject}
                onCreated={() => api.documents.list(selectedProject).then(setDocs).catch(console.error)}
              />
            </div>
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
