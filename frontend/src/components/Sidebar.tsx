import { useEffect, useState } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Project, type DocumentMeta } from '@/lib/api'

export function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [docs, setDocs] = useState<DocumentMeta[]>([])

  useEffect(() => {
    api.projects.list().then(setProjects).catch(console.error)
  }, [])

  useEffect(() => {
    if (selectedProject) {
      api.documents.list(selectedProject).then(setDocs).catch(console.error)
    }
  }, [selectedProject])

  return (
    <aside className="w-[280px] border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold">Datum</h1>
      </div>
      <ScrollArea className="flex-1">
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
        </div>
        {selectedProject && docs.length > 0 && (
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
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
