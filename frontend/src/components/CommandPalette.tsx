import { useEffect, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { openTemplateDialog } from '@/components/CreateDocumentDialog'
import { api, type DocumentMeta } from '@/lib/api'
import {
  buildProjectSwitchTarget,
  describeProjectVisit,
  navigateToProjectTarget,
} from '@/lib/project-navigation'
import { useProjectCreation } from '@/lib/project-creation'
import { useProjectPreferences } from '@/lib/project-preferences'
import { queryKeys } from '@/lib/query-keys'
import { resolveSelectedProject } from '@/lib/route-project'
import {
  createSearchDraftForLaunch,
  createSearchRouteStateForLaunch,
  routeSearchFromDraft,
} from '@/lib/search-route'
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

const GROUP_HEADING =
  '[&_[cmdk-group-heading]]:pb-[4px] [&_[cmdk-group-heading]]:pl-[14px] [&_[cmdk-group-heading]]:pt-[10px] [&_[cmdk-group-heading]]:text-[9px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-[#666]'

const ITEM_BASE =
  'flex items-center gap-[10px] px-[14px] py-[8px] text-[12px] text-[#333] cursor-pointer data-[selected=true]:bg-[rgba(34,165,241,0.06)] data-[selected=true]:shadow-[inset_0_0_0_1px_#22a5f1]'

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const { openCreateProjectDialog } = useProjectCreation()
  const preferences = useProjectPreferences()

  const selectedProject = resolveSelectedProject(location.pathname, location.searchStr)

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
      setQuery('')
    }
  }, [open])

  const projectsQuery = useProjectsQuery()
  const projects = open ? (projectsQuery.data ?? []) : []
  const normalizedQuery = query.trim().replace(/^\/+/, '')
  const searching = Boolean(normalizedQuery)

  const projectBySlug = useMemo(
    () => new Map(projects.map((project) => [project.slug, project])),
    [projects],
  )

  const projectRows = useMemo(() => {
    if (searching) {
      return projects.filter((project) => {
        const loweredQuery = normalizedQuery.toLowerCase()
        return (
          project.name.toLowerCase().includes(loweredQuery) ||
          project.slug.toLowerCase().includes(loweredQuery) ||
          (project.description ?? '').toLowerCase().includes(loweredQuery)
        )
      })
    }

    const preferred = new Map<string, (typeof projects)[number]>()
    if (selectedProject && projectBySlug.get(selectedProject)) {
      preferred.set(selectedProject, projectBySlug.get(selectedProject)!)
    }
    for (const slug of preferences.pinnedSlugs) {
      const project = projectBySlug.get(slug)
      if (project) preferred.set(slug, project)
    }
    for (const entry of preferences.recent) {
      const project = projectBySlug.get(entry.slug)
      if (project) preferred.set(entry.slug, project)
    }
    return [...preferred.values()].slice(0, 4)
  }, [searching, projects, normalizedQuery, selectedProject, preferences.pinnedSlugs, preferences.recent, projectBySlug])

  const contentProjects = useMemo(
    () =>
      selectedProject
        ? projects.filter((project) => project.slug === selectedProject)
        : projects,
    [projects, selectedProject],
  )

  const workspaceQueries = useQueries({
    queries: open && searching
      ? contentProjects.map((project) => ({
          queryKey: queryKeys.workspace(project.slug),
          queryFn: () => api.projects.workspace(project.slug),
        }))
      : [],
  })

  const documents = useMemo(
    () =>
      workspaceQueries.flatMap((query) => {
        if (!query.data) return []
        return query.data.documents.map((document) => ({
          ...document,
          project_slug: query.data.project.slug,
        }))
      }),
    [workspaceQueries],
  )

  const entitySeed = useMemo(
    () => contentProjects.map((project) => project.slug).join('|'),
    [contentProjects],
  )

  const entitiesQuery = useQuery({
    queryKey: queryKeys.commandPaletteEntities(selectedProject, entitySeed),
    enabled: open && searching && contentProjects.length > 0,
    queryFn: async () => {
      const summaries = await Promise.all(
        contentProjects.map(async (project) => ({
          projectSlug: project.slug,
          summary: await api.intelligence.summary(project.slug),
        })),
      )

      const nextEntities: CommandEntity[] = []
      const seen = new Set<string>()
      for (const item of summaries) {
        for (const entity of item.summary.key_entities) {
          const key = `${item.projectSlug}:${entity.entity_type}:${entity.canonical_name}`
          if (seen.has(key)) continue
          seen.add(key)
          nextEntities.push({
            projectSlug: item.projectSlug,
            rawText: entity.canonical_name,
            termType: entity.entity_type,
          })
        }
      }
      return nextEntities.slice(0, 8)
    },
  })
  const entities = entitiesQuery.data ?? []

  const matchedDocuments = useMemo(() => {
    if (!searching) return []
    const loweredQuery = normalizedQuery.toLowerCase()
    return documents.filter((document) => {
      const title = document.title.toLowerCase()
      const path = document.relative_path.toLowerCase()
      return title.includes(loweredQuery) || path.includes(loweredQuery)
    }).slice(0, 6)
  }, [documents, normalizedQuery, searching])

  const buildPaletteSearchState = (project?: string | null) => {
    if (!normalizedQuery) {
      return createSearchRouteStateForLaunch(project)
    }

    return routeSearchFromDraft({
      ...createSearchDraftForLaunch(project),
      query: normalizedQuery,
    })
  }

  const close = () => setOpen(false)

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-[rgba(27,36,49,0.5)]" onClick={close}>
      <div
        className="mx-auto mt-[82px] w-[425px]"
        onClick={(event) => event.stopPropagation()}
      >
        <Command className="flex max-h-[420px] min-h-[320px] flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_30px_0px_rgba(0,0,0,0.25)]">
          <div className="flex shrink-0 items-center justify-between bg-[#22a5f1] px-[14px] py-[10px]">
            <span className="text-[14px] font-semibold text-white">Omni-Search</span>
            <button
              type="button"
              onClick={close}
              className="text-[16px] text-white/80 hover:text-white"
            >
              {'\u2715'}
            </button>
          </div>

          <div className="shrink-0 border-b border-[#e1e8ed] px-[12px] py-[12px]">
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder="/  project, tag, or recent..."
              className="min-h-[70px] w-full rounded-[3px] border border-[#22a5f1] bg-white px-[10px] py-[10px] text-[12px] text-[#333] outline-none placeholder:text-[#999]"
            />
          </div>

          <div className="shrink-0 border-b border-[#e1e8ed] bg-[#f3f6f8] px-[14px] py-[10px] text-[10px] text-[#666]">
            Context: <span className="text-[#22a5f1]">projects, recent items, and creation actions</span>
          </div>

          <Command.List className="min-h-0 flex-1 overflow-auto py-[4px]">
            <Command.Empty className="px-[20px] py-[16px] text-[11px] text-[#666]">
              No matches.
            </Command.Empty>

            <Command.Group heading="PROJECTS" className={GROUP_HEADING}>
              {projectRows.map((project) => {
                const recentEntry = preferences.recent.find((entry) => entry.slug === project.slug)
                const subtitle = recentEntry
                  ? describeProjectVisit(recentEntry)
                  : project.description || project.slug
                const meta =
                  project.slug === selectedProject
                    ? 'Current'
                    : preferences.pinnedSlugs.includes(project.slug)
                      ? 'Pinned'
                      : undefined

                return (
                  <Command.Item
                    key={project.slug}
                    value={`project ${project.name} ${project.slug}`}
                    onSelect={() => {
                      close()
                      navigateToProjectTarget(
                        navigate,
                        buildProjectSwitchTarget(location.pathname, location.searchStr, project.slug),
                      )
                    }}
                    className={ITEM_BASE}
                  >
                    <div className="h-4 w-[3px] shrink-0 rounded-full bg-[#22a5f1]" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12px] font-semibold">{project.name}</div>
                      <div className="truncate text-[10px] text-[#7b8794]">{subtitle}</div>
                    </div>
                    {meta ? <span className="text-[10px] text-[#666]">{meta}</span> : null}
                  </Command.Item>
                )
              })}
            </Command.Group>

            {searching && matchedDocuments.length > 0 && (
              <>
                <div className="mx-0 my-0 h-px w-full bg-[#e1e8ed]" />
                <Command.Group heading="DOCUMENTS" className={GROUP_HEADING}>
                  {matchedDocuments.map((document) => (
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
                      className={ITEM_BASE}
                    >
                      <span className="size-[6px] shrink-0 rounded-full bg-[#22a5f1]" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[12px]">{document.title}</div>
                        <div className="truncate text-[10px] text-[#7b8794]">{document.relative_path}</div>
                      </div>
                    </Command.Item>
                  ))}
                </Command.Group>
              </>
            )}

            <div className="mx-0 my-0 h-px w-full bg-[#e1e8ed]" />

            <Command.Group heading="ACTIONS" className={GROUP_HEADING}>
              <Command.Item
                value="create project"
                onSelect={() => {
                  close()
                  openCreateProjectDialog({ source: 'command-palette' })
                }}
                className={ITEM_BASE}
              >
                <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                Create Project
              </Command.Item>

              <Command.Item
                value="projects home"
                onSelect={() => {
                  close()
                  navigate({ to: '/' })
                }}
                className={ITEM_BASE}
              >
                <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                Open Projects Home
              </Command.Item>

              <Command.Item
                value={`search all projects ${normalizedQuery}`}
                onSelect={() => {
                  close()
                  navigate({
                    to: '/search',
                    search: buildPaletteSearchState(),
                  })
                }}
                className={ITEM_BASE}
              >
                <span className="size-[6px] shrink-0 rounded-full bg-[#333]" />
                Search All Projects
              </Command.Item>

              {selectedProject && (
                <>
                  <Command.Item
                    value={`search current project ${selectedProject} ${normalizedQuery}`}
                    onSelect={() => {
                      close()
                      navigate({
                        to: '/search',
                        search: buildPaletteSearchState(selectedProject),
                      })
                    }}
                    className={ITEM_BASE}
                  >
                    <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                    Search Current Project
                  </Command.Item>
                  <Command.Item
                    value={`create adr ${selectedProject}`}
                    onSelect={() => {
                      close()
                      openTemplateDialog('adr')
                    }}
                    className={ITEM_BASE}
                  >
                    <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                    New Decision (ADR)
                  </Command.Item>
                </>
              )}
            </Command.Group>

            {searching && entities.length > 0 && (
              <>
                <div className="mx-0 my-0 h-px w-full bg-[#e1e8ed]" />
                <Command.Group heading="ENTITIES" className={GROUP_HEADING}>
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
                      className={ITEM_BASE}
                    >
                      <span className="size-[6px] shrink-0 rounded-full bg-[#22a5f1]" />
                      <span className="flex-1 text-[12px]">{entity.rawText}</span>
                      <span className="text-[10px] text-[#7b8794]">{entity.termType}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              </>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
