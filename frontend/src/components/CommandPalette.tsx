import { useEffect, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { openTemplateDialog } from '@/components/CreateDocumentDialog'
import { api, type DocumentMeta } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import { resolveSelectedProject } from '@/lib/route-project'
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
  '[&_[cmdk-group-heading]]:pb-[4px] [&_[cmdk-group-heading]]:pl-[20px] [&_[cmdk-group-heading]]:pt-[10px] [&_[cmdk-group-heading]]:text-[9px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-[#666]'

const ITEM_BASE =
  'flex items-center gap-[10px] px-[20px] py-[8px] text-[13px] text-[#333] cursor-pointer data-[selected=true]:bg-[rgba(34,165,241,0.06)] data-[selected=true]:border-l-[3px] data-[selected=true]:border-[#22a5f1]'

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

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
  const visibleProjects = useMemo(
    () =>
      selectedProject
        ? projects.filter((project) => project.slug === selectedProject)
        : projects,
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
        if (!query.data) return []
        return query.data.documents.map((document) => ({
          ...document,
          project_slug: query.data.project.slug,
        }))
      }),
    [workspaceQueries],
  )

  const entitySeed = useMemo(
    () => visibleProjects.map((project) => project.slug).join('|'),
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
          if (seen.has(key)) continue
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
  const normalizedQuery = query.trim().replace(/^\/+/, '')
  const detectedEntity = useMemo(() => {
    if (!normalizedQuery) {
      return null
    }

    const loweredQuery = normalizedQuery.toLowerCase()
    return (
      entities.find((entity) => {
        const candidate = entity.rawText.toLowerCase()
        return candidate.includes(loweredQuery) || loweredQuery.includes(candidate)
      }) ?? {
        projectSlug: selectedProject ?? visibleProjects[0]?.slug ?? '',
        rawText: normalizedQuery,
        termType: 'tags',
      }
    )
  }, [entities, normalizedQuery, selectedProject, visibleProjects])
  const decisionReferenceCount = useMemo(() => {
    if (!normalizedQuery) {
      return 0
    }
    const loweredQuery = normalizedQuery.toLowerCase()
    return documents.filter((document) => {
      if (document.doc_type !== 'decision') {
        return false
      }
      const title = document.title.toLowerCase()
      const path = document.relative_path.toLowerCase()
      return title.includes(loweredQuery) || path.includes(loweredQuery)
    }).length
  }, [documents, normalizedQuery])

  const close = () => setOpen(false)

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-[rgba(27,36,49,0.5)]" onClick={close}>
      <div
        className="mx-auto mt-[82px] w-[440px]"
        onClick={(event) => event.stopPropagation()}
      >
        <Command className="flex max-h-[420px] min-h-[320px] flex-col overflow-hidden rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_30px_0px_rgba(0,0,0,0.25)]">
          {/* Blue header */}
          <div className="flex shrink-0 items-center justify-between bg-[#22a5f1] px-[20px] py-[12px]">
            <span className="text-[14px] font-semibold text-white">Omni-Search</span>
            <button
              type="button"
              onClick={close}
              className="text-[16px] text-white/80 hover:text-white"
            >
              {'\u2715'}
            </button>
          </div>

          {/* Search input */}
          <div className="shrink-0 border-b border-[#e1e8ed] px-[20px] py-[14px]">
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder="Open a document, search, create an ADR, jump to an entity..."
              className="w-full rounded-[4px] border border-[#22a5f1] bg-white px-[12px] py-[8px] text-[13px] text-[#333] outline-none placeholder:text-[#999]"
            />
          </div>

          {normalizedQuery && (
            <div className="shrink-0 border-b border-[#e1e8ed] bg-[#f3f6f8] px-[14px] py-[12px] text-[10px] text-[#666]">
              Detecting Intent...{' '}
              {detectedEntity ? (
                <span className="text-[#22a5f1]">
                  Entity: &lsquo;{detectedEntity.rawText}&rsquo; (type: {detectedEntity.termType})
                </span>
              ) : (
                <span className="text-[#22a5f1]">Searching documents and actions</span>
              )}
            </div>
          )}

          {/* Results */}
          <Command.List className="min-h-0 flex-1 overflow-auto py-[4px]">
            <Command.Empty className="px-[20px] py-[16px] text-[11px] text-[#666]">
              No matches.
            </Command.Empty>

            {/* Documents (FIND) */}
            <Command.Group heading="FIND" className={GROUP_HEADING}>
              {documents
                .filter((document) =>
                  selectedProject ? document.project_slug === selectedProject : true,
                )
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
                    className={ITEM_BASE}
                  >
                    <div className="flex min-w-0 flex-col gap-[2px]">
                      <span className="truncate text-[13px]">{document.title}</span>
                      <span className="truncate text-[10px] text-[#999]">
                        {document.relative_path}
                      </span>
                    </div>
                  </Command.Item>
                ))}
            </Command.Group>

            {normalizedQuery && decisionReferenceCount > 0 && (
              <div className="border-t border-[#e1e8ed] px-[20px] py-[8px]">
                <div className="text-[12px] text-[#333]">
                  Decisions referencing &lsquo;{normalizedQuery}&rsquo;
                </div>
                <div className="text-[10px] text-[#999]">{decisionReferenceCount} results</div>
              </div>
            )}

            {/* Divider between groups */}
            <div className="mx-0 my-0 h-px w-full bg-[#e1e8ed]" />

            {/* Actions */}
            <Command.Group heading="ACTIONS" className={GROUP_HEADING}>
              <Command.Item
                value="search"
                onSelect={() => {
                  close()
                  navigate({ to: '/search' })
                }}
                className={ITEM_BASE}
              >
                <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
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
                    className={ITEM_BASE}
                  >
                    <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                    New Decision (ADR)
                  </Command.Item>
                  <Command.Item
                    value={`new session notes ${selectedProject}`}
                    onSelect={() => {
                      close()
                      openTemplateDialog('session-note')
                    }}
                    className={ITEM_BASE}
                  >
                    <span className="size-[6px] shrink-0 rounded-full bg-[#5cb85c]" />
                    New Session Notes
                  </Command.Item>
                  <Command.Item
                    value={`review inbox ${selectedProject}`}
                    onSelect={() => {
                      close()
                      navigate({
                        to: '/projects/$slug/inbox',
                        params: { slug: selectedProject },
                      })
                    }}
                    className={ITEM_BASE}
                  >
                    <span className="size-[6px] shrink-0 rounded-full bg-[#22a5f1]" />
                    Go to Inbox
                  </Command.Item>
                </>
              )}

              {visibleProjects.map((project) => (
                <Command.Item
                  key={project.slug}
                  value={`project ${project.name} ${project.slug}`}
                  onSelect={() => {
                    close()
                    navigate({
                      to: '/projects/$slug',
                      params: { slug: project.slug },
                    })
                  }}
                  className={ITEM_BASE}
                >
                  <span className="size-[6px] shrink-0 rounded-full bg-[#22a5f1]" />
                  <span className="flex-1">{project.name}</span>
                  <span className="text-[10px] text-[#999]">{project.slug}</span>
                </Command.Item>
              ))}
            </Command.Group>

            {entities.length > 0 && (
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
                      <span className="flex-1 text-[13px]">{entity.rawText}</span>
                      <span className="text-[10px] text-[#999]">{entity.termType}</span>
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
