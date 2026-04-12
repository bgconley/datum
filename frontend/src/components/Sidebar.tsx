import { useEffect, useState, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Project, type DocumentMeta } from '@/lib/api'
import { CreateProjectDialog } from './CreateProjectDialog'
import { CreateDocumentDialog } from './CreateDocumentDialog'

export function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [docs, setDocs] = useState<DocumentMeta[]>([])

  const loadProjects = useCallback(() => {
    api.projects.list().then(setProjects).catch(console.error)
  }, [])

  const loadDocs = useCallback(() => {
    if (selectedProject) {
      api.documents.list(selectedProject).then(setDocs).catch(console.error)
    }
  }, [selectedProject])

  useEffect(() => { loadProjects() }, [loadProjects])
  useEffect(() => { loadDocs() }, [loadDocs])

  return (
    <aside className="w-[280px] border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold">Datum</h1>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 border-b border-border">
          <a
            href="#/search"
            className="flex items-center gap-2 rounded px-2 py-2 text-sm hover:bg-accent"
          >
            <span>Search</span>
            <kbd className="ml-auto rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">
              /
            </kbd>
          </a>
        </div>
        <div className="p-2">
          <h2 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase">
            Projects
          </h2>
          {projects.map((p) => (
            <button
              key={p.slug}
              onClick={() => setSelectedProject(p.slug)}
              className={`w-full text-left px-2 py-1.5 rounded text-sm hover:bg-accent ${
                selectedProject === p.slug ? 'bg-accent' : ''
              }`}
            >
              {p.name}
            </button>
          ))}
          <div className="mt-2 px-1">
            <CreateProjectDialog onCreated={loadProjects} />
          </div>
        </div>
        {selectedProject && (
          <div className="p-2 border-t border-border">
            <h2 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase">
              Documents
            </h2>
            {docs.map((d) => (
              <a
                key={d.relative_path}
                href={`#/${selectedProject}/${d.relative_path}`}
                className="block px-2 py-1.5 rounded text-sm hover:bg-accent truncate"
              >
                {d.title}
              </a>
            ))}
            <div className="mt-2 px-1">
              <CreateDocumentDialog projectSlug={selectedProject} onCreated={loadDocs} />
            </div>
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
