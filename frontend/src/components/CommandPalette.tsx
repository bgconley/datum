import { useEffect, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import { X } from 'lucide-react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { openTemplateDialog } from '@/components/CreateDocumentDialog'
import { api, type DocumentMeta } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { useProjectsQuery } from '@/lib/workspace-query'

interface CommandDocument extends DocumentMeta {
  project_slug: string
}

interface CommandEntity {
  projectSlug: string
  rawText: string
  termType: string
}

const TOGGLE_EVENT = 'datum:toggle-command-palette'

export function toggleCommandPalette() {
  window.dispatchEvent(new CustomEvent(TOGGLE_EVENT))
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const selectedProject = location.pathname.startsWith('/projects/')
    ? decodeURIComponent(location.pathname.split('/')[2] ?? '')
    : null

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

  const projectsQuery = useProjectsQuery()
  const projects = open ? (projectsQuery.data ?? []) : []
  const visibleProjects = useMemo(
    () => (selectedProject ? projects.filter((project) => project.slug === selectedProject) : projects),
    [projects, selectedProject],
  )

  const workspaceQueries = useQueries({
    queries: open
      ? visibleProjects.map((project) => ({
          queryKey: queryKeys.workspace(project.slug),
          queryFn: () => api.projects.workspace(project.slug),
        }))
      : [],
  })

  const documents = useMemo(
    () =>
      workspaceQueries.flatMap((query) => {
        if (!query.data) {
          return []
        }

        return query.data.documents.map((document) => ({
          ...document,
          project_slug: query.data.project.slug,
        }))
      }),
    [workspaceQueries],
  )

  const entitySeed = useMemo(
    () =>
      visibleProjects
        .map((project) => project.slug)
        .join('|'),
    [visibleProjects],
  )

  const entitiesQuery = useQuery({
    queryKey: queryKeys.commandPaletteEntities(selectedProject, entitySeed),
    enabled: open && visibleProjects.length > 0,
    queryFn: async () => {
      const summaries = await Promise.all(
        visibleProjects.map(async (project) => ({
          projectSlug: project.slug,
          summary: await api.intelligence.summary(project.slug),
        })),
      )

      const nextEntities: CommandEntity[] = []
      const seen = new Set<string>()
      for (const item of summaries) {
        for (const entity of item.summary.key_entities) {
          const key = `${item.projectSlug}:${entity.entity_type}:${entity.canonical_name}`
          if (seen.has(key)) {
            continue
          }
          seen.add(key)
          nextEntities.push({
            projectSlug: item.projectSlug,
            rawText: entity.canonical_name,
            termType: entity.entity_type,
          })
        }
      }
      return nextEntities.slice(0, 16)
    },
  })
  const entities = entitiesQuery.data ?? []

  const close = () => setOpen(false)

  if (!open) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/20"
      onClick={close}
    >
      <div
        className="mx-auto mt-[14vh] w-full max-w-2xl px-4"
        onClick={(event) => event.stopPropagation()}
      >
        <Command className="overflow-hidden rounded border border-border bg-white shadow-2xl">
          <div className="flex items-center justify-between bg-primary px-5 py-3">
            <span className="text-sm font-semibold text-white">Omni-Search</span>
            <button type="button" onClick={close} className="text-white/80 hover:text-white">
              <X className="size-4" />
            </button>
          </div>
          <Command.Input
            autoFocus
            placeholder="Open a document, search, create an ADR, jump to an entity…"
            className="h-14 w-full border-b border-border bg-white px-5 text-sm outline-none focus:ring-2 focus:ring-primary"
          />
          <Command.List className="max-h-[24rem] overflow-auto p-3">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
              No matches.
            </Command.Empty>

            <Command.Group
              heading="Actions"
              className="mb-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-muted-foreground"
            >
              <Command.Item
                value="search"
                onSelect={() => {
                  close()
                  navigate({ to: '/search' })
                }}
                className="flex items-center gap-2 rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
              >
                <span className="size-2 rounded-full bg-green-500" />
                Search workspace
              </Command.Item>

              {selectedProject && (
                <>
                  <Command.Item
                    value={`create adr ${selectedProject}`}
                    onSelect={() => {
                      close()
                      openTemplateDialog('adr')
                    }}
                    className="flex items-center gap-2 rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
                  >
                    <span className="size-2 rounded-full bg-green-500" />
                    Create ADR
                  </Command.Item>
                  <Command.Item
                    value={`review inbox ${selectedProject}`}
                    onSelect={() => {
                      close()
                      navigate({ to: '/projects/$slug/inbox', params: { slug: selectedProject } })
                    }}
                    className="flex items-center gap-2 rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
                  >
                    <span className="size-2 rounded-full bg-green-500" />
                    Review inbox
                  </Command.Item>
                </>
              )}
            </Command.Group>

            <Command.Group
              heading="Projects"
              className="mb-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-muted-foreground"
            >
              {visibleProjects.map((project) => (
                <Command.Item
                  key={project.slug}
                  value={`project ${project.name} ${project.slug}`}
                  onSelect={() => {
                    close()
                    navigate({ to: '/projects/$slug', params: { slug: project.slug } })
                  }}
                  className="rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span>{project.name}</span>
                    <span className="text-xs text-muted-foreground">{project.slug}</span>
                  </div>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group
              heading="Documents"
              className="mb-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-muted-foreground"
            >
              {documents
                .filter((document) => (selectedProject ? document.project_slug === selectedProject : true))
                .map((document) => (
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
                    className="rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
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

            {entities.length > 0 && (
              <Command.Group
                heading="Entities"
                className="[&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-muted-foreground"
              >
                {entities.map((entity) => (
                  <Command.Item
                    key={`${entity.projectSlug}:${entity.termType}:${entity.rawText}`}
                    value={`entity ${entity.rawText} ${entity.termType}`}
                    onSelect={() => {
                      close()
                      navigate({
                        to: '/search',
                        search: {
                          query: entity.rawText,
                          project: entity.projectSlug,
                        },
                      })
                    }}
                    className="rounded px-3 py-2 text-sm data-[selected=true]:bg-primary/10 data-[selected=true]:border-l-2 data-[selected=true]:border-primary"
                  >
                    <div className="flex w-full items-center justify-between gap-3">
                      <span>{entity.rawText}</span>
                      <span className="text-xs text-muted-foreground">{entity.termType}</span>
                    </div>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
