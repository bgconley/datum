import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from '@tanstack/react-router'

import { api, type DocumentMeta, type Project } from '@/lib/api'

interface CommandDocument extends DocumentMeta {
  project_slug: string
}

const TOGGLE_EVENT = 'datum:toggle-command-palette'

export function toggleCommandPalette() {
  window.dispatchEvent(new CustomEvent(TOGGLE_EVENT))
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [documents, setDocuments] = useState<CommandDocument[]>([])
  const navigate = useNavigate()

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((current) => !current)
      }
    }

    const handleToggle = () => setOpen((current) => !current)

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener(TOGGLE_EVENT, handleToggle)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener(TOGGLE_EVENT, handleToggle)
    }
  }, [])

  useEffect(() => {
    if (!open) {
      return
    }

    api.projects.list().then(setProjects).catch(console.error)
  }, [open])

  useEffect(() => {
    if (!open || projects.length === 0) {
      return
    }

    Promise.all(
      projects.map((project) =>
        api.documents
          .list(project.slug)
          .then((docs) =>
            docs.map((document) => ({ ...document, project_slug: project.slug })),
          ),
      ),
    )
      .then((results) => setDocuments(results.flat()))
      .catch(console.error)
  }, [open, projects])

  if (!open) {
    return null
  }

  const close = () => setOpen(false)

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
      onClick={close}
    >
      <div
        className="mx-auto mt-[14vh] w-full max-w-2xl px-4"
        onClick={(event) => event.stopPropagation()}
      >
        <Command className="overflow-hidden rounded-[1.5rem] border border-border/80 bg-card shadow-2xl">
          <Command.Input
            autoFocus
            placeholder="Jump to search, a project, or a document…"
            className="h-14 w-full border-b border-border bg-transparent px-5 text-sm outline-none"
          />
          <Command.List className="max-h-[24rem] overflow-auto p-3">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
              No matches.
            </Command.Empty>

            <Command.Group heading="Actions" className="mb-3">
              <Command.Item
                value="search"
                onSelect={() => {
                  close()
                  navigate({ to: '/search' })
                }}
                className="rounded-xl px-3 py-2 text-sm data-[selected=true]:bg-accent"
              >
                Search documents
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Projects" className="mb-3">
              {projects.map((project) => (
                <Command.Item
                  key={project.slug}
                  value={`project ${project.name} ${project.slug}`}
                  onSelect={() => {
                    close()
                    navigate({ to: '/projects/$slug', params: { slug: project.slug } })
                  }}
                  className="rounded-xl px-3 py-2 text-sm data-[selected=true]:bg-accent"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span>{project.name}</span>
                    <span className="text-xs text-muted-foreground">{project.slug}</span>
                  </div>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Documents">
              {documents.map((document) => (
                <Command.Item
                  key={`${document.project_slug}:${document.relative_path}`}
                  value={`document ${document.title} ${document.project_slug} ${document.relative_path}`}
                  onSelect={() => {
                    close()
                    navigate({
                      to: '/projects/$slug/docs/$',
                      params: {
                        slug: document.project_slug,
                        _splat: document.relative_path,
                      },
                    })
                  }}
                  className="rounded-xl px-3 py-2 text-sm data-[selected=true]:bg-accent"
                >
                  <div className="min-w-0">
                    <div className="truncate">{document.title}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {document.project_slug} / {document.relative_path}
                    </div>
                  </div>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
