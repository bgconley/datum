import { useMemo } from 'react'
import { Clock3, FolderPlus, Pin, PinOff, Search } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import type { Project } from '@/lib/api'
import { useProjectCreation } from '@/lib/project-creation'
import {
  buildProjectSwitchTarget,
  buildResumeTarget,
  describeProjectVisit,
  navigateToProjectTarget,
} from '@/lib/project-navigation'
import {
  isProjectPinned,
  togglePinnedProject,
  useProjectPreferences,
} from '@/lib/project-preferences'
import { createSearchRouteStateForLaunch } from '@/lib/search-route'
import { useProjectsQuery } from '@/lib/workspace-query'

function formatRelativeVisit(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'Recently'
  }

  const minutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000))
  if (minutes < 60) {
    return `${minutes} min ago`
  }
  const hours = Math.round(minutes / 60)
  if (hours < 24) {
    return `${hours}h ago`
  }
  return date.toLocaleDateString()
}

function countProjectsNeedingSetup(projects: Project[]) {
  return projects.filter((project) => project.status.toLowerCase() !== 'active').length
}

function sortProjects(projects: Project[]) {
  return [...projects].sort((left, right) => left.name.localeCompare(right.name))
}

function projectSummary(project: Project) {
  if (project.description?.trim()) {
    return project.description.trim()
  }
  if (project.tags.length > 0) {
    return project.tags.join(', ')
  }
  if (project.status.toLowerCase() !== 'active') {
    return 'No docs yet — created but not onboarded'
  }
  return 'Workspace ready for documents, search, and review'
}

function ProjectStatus({ status }: { status: string }) {
  const tone =
    status.toLowerCase() === 'active'
      ? 'text-[#3c763d]'
      : status.toLowerCase().includes('attention')
        ? 'text-[#d9534f]'
        : 'text-[#666]'

  return <span className={`text-[12px] font-medium ${tone}`}>{status}</span>
}

function ProjectRow({
  project,
  pinned,
  onOpen,
  onTogglePinned,
}: {
  project: Project
  pinned: boolean
  onOpen: () => void
  onTogglePinned: () => void
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_120px_96px] items-start gap-4 border-t border-[#e1e8ed] px-4 py-3 first:border-t-0">
      <div className="group flex min-w-0 items-start gap-3">
        <button type="button" className="flex min-w-0 flex-1 items-start gap-3 text-left" onClick={onOpen}>
          <div className="mt-[4px] h-5 w-[3px] shrink-0 rounded-full bg-[#22a5f1]" />
          <div className="min-w-0">
            <div className="truncate text-[14px] font-semibold text-[#1b2431]">
              {project.name}
            </div>
            <div className="truncate text-[11px] text-[#7b8794]">{projectSummary(project)}</div>
          </div>
        </button>
        <button
          type="button"
          aria-label={pinned ? `Unpin ${project.name}` : `Pin ${project.name}`}
          className="mt-0.5 text-[#999] opacity-0 transition hover:text-[#22a5f1] group-hover:opacity-100"
          onClick={onTogglePinned}
        >
          {pinned ? <Pin className="size-3.5 fill-current" /> : <PinOff className="size-3.5" />}
        </button>
      </div>
      <div className="text-[12px] text-[#666]">{project.created?.slice(0, 10) ?? '—'}</div>
      <ProjectStatus status={project.status} />
    </div>
  )
}

export function ProjectsHome() {
  const navigate = useNavigate()
  const { openCreateProjectDialog } = useProjectCreation()
  const projectsQuery = useProjectsQuery()
  const preferences = useProjectPreferences()
  const projects = projectsQuery.data ?? []

  const projectBySlug = useMemo(
    () => new Map(projects.map((project) => [project.slug, project])),
    [projects],
  )

  const sortedProjects = useMemo(() => sortProjects(projects), [projects])

  const pinnedProjects = useMemo(
    () =>
      preferences.pinnedSlugs
        .map((slug) => projectBySlug.get(slug))
        .filter((project): project is Project => Boolean(project)),
    [preferences.pinnedSlugs, projectBySlug],
  )

  const recentProjects = useMemo(
    () =>
      preferences.recent
        .map((entry) => {
          const project = projectBySlug.get(entry.slug)
          if (!project) {
            return null
          }
          return { entry, project }
        })
        .filter(
          (item): item is { entry: (typeof preferences.recent)[number]; project: Project } =>
            Boolean(item),
        ),
    [preferences.recent, projectBySlug],
  )

  const resumeProject = useMemo(() => {
    const lastOpened = preferences.lastOpenedSlug
      ? projectBySlug.get(preferences.lastOpenedSlug)
      : null
    if (!lastOpened) {
      return recentProjects[0] ?? (sortedProjects[0] ? { entry: null, project: sortedProjects[0] } : null)
    }
    const recentEntry = preferences.recent.find((entry) => entry.slug === lastOpened.slug)
    return recentEntry ? { entry: recentEntry, project: lastOpened } : { entry: null, project: lastOpened }
  }, [preferences.lastOpenedSlug, preferences.recent, projectBySlug, recentProjects, sortedProjects])

  const homePinnedProjects = pinnedProjects.length > 0 ? pinnedProjects.slice(0, 3) : sortedProjects.slice(0, 3)
  const homeRecentProjects =
    recentProjects.length > 0
      ? recentProjects.slice(0, 3)
      : sortedProjects.slice(0, 3).map((project) => ({ entry: null, project }))

  const openProjectDashboard = (slug: string) => {
    navigateToProjectTarget(
      navigate,
      buildProjectSwitchTarget('/', '', slug),
    )
  }

  if (projectsQuery.isLoading) {
    return <div className="p-8 text-[#666]">Loading projects…</div>
  }

  if (projects.length === 0) {
    return (
      <div className="min-h-full bg-[#f3f6f8] p-6">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-5">
          <div>
            <h1 className="text-[18px] font-semibold text-[#1b2431]">Projects</h1>
            <p className="mt-1 text-[12px] text-[#7b8794]">
              Create the first project cabinet to start capturing documents, decisions, and search context.
            </p>
          </div>

          <div className="flex min-h-[420px] items-center justify-center">
            <div className="w-full max-w-[760px] rounded-[4px] border border-[#e1e8ed] bg-white px-10 py-12 shadow-sm">
              <div className="mx-auto flex h-[58px] w-[58px] items-center justify-center rounded-full bg-[#f3f6f8] text-[#22a5f1]">
                <FolderPlus className="size-6" />
              </div>
              <h2 className="mt-4 text-center text-[22px] font-semibold text-[#1b2431]">
                No projects yet
              </h2>
              <p className="mx-auto mt-3 max-w-[560px] text-center text-[13px] leading-6 text-[#7b8794]">
                Datum organizes knowledge by project. Create a cabinet first, then upload source material,
                start a brief, or run grounded search inside the new workspace.
              </p>
              <div className="mt-6 flex justify-center gap-3">
                <Button
                  type="button"
                  className="gap-2 bg-[#22a5f1] text-white hover:bg-[#1a94db]"
                  onClick={() => openCreateProjectDialog({ source: 'projects-home' })}
                >
                  <FolderPlus className="size-4" />
                  Create Project
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="gap-2 border-[#d6e0e8] bg-white text-[#1b2431]"
                  onClick={() =>
                    document
                      .getElementById('empty-project-workflow')
                      ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                  }
                >
                  <Search className="size-4" />
                  View Workflow
                </Button>
              </div>
              <div
                id="empty-project-workflow"
                className="mx-auto mt-6 max-w-[470px] border-t border-[#e1e8ed] pt-5 text-[12px] leading-6 text-[#666]"
              >
                <div className="font-semibold text-[#1b2431]">1. Create the project record</div>
                <div className="text-[#7b8794]">
                  Name it, confirm the slug, and add a short description.
                </div>
                <div className="mt-3 font-semibold text-[#1b2431]">2. Land on the dashboard</div>
                <div className="text-[#7b8794]">
                  The new project opens with onboarding actions for Upload, Create Document, and Search.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full bg-[#f3f6f8] p-6">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-[18px] font-semibold text-[#1b2431]">Projects</h1>
            <p className="mt-1 text-[12px] text-[#7b8794]">
              Resume active work, switch cabinets, or create a new project workspace.
            </p>
          </div>
          <Button
            type="button"
            className="gap-2 bg-[#22a5f1] text-white hover:bg-[#1a94db]"
            onClick={() => openCreateProjectDialog({ source: 'projects-home' })}
          >
            <FolderPlus className="size-4" />
            New Project
          </Button>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_265px] gap-5">
          <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-5 py-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              WORKSPACE HOME
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Resume Last Project</div>
            {resumeProject ? (
              <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[16px] font-semibold text-[#1b2431]">
                    {resumeProject.project.name}
                  </div>
                  <div className="mt-2 text-[11px] text-[#7b8794]">
                    {resumeProject.entry
                      ? `${formatRelativeVisit(resumeProject.entry.visitedAt)} • ${describeProjectVisit(
                          resumeProject.entry,
                        )}`
                      : projectSummary(resumeProject.project)}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      className="h-8 bg-[#22a5f1] px-3 text-[12px] text-white hover:bg-[#1a94db]"
                      onClick={() => {
                        if (resumeProject.entry) {
                          navigateToProjectTarget(navigate, buildResumeTarget(resumeProject.entry))
                          return
                        }
                        openProjectDashboard(resumeProject.project.slug)
                      }}
                    >
                      Open Dashboard
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 border-[#d6e0e8] bg-white px-3 text-[12px] text-[#1b2431]"
                      onClick={() =>
                        navigate({
                          to: '/projects/$slug/inbox',
                          params: { slug: resumeProject.project.slug },
                        })
                      }
                    >
                      Open Inbox
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 border-[#d6e0e8] bg-white px-3 text-[12px] text-[#1b2431]"
                      onClick={() =>
                        navigate({
                          to: '/search',
                          search: createSearchRouteStateForLaunch(resumeProject.project.slug),
                        })
                      }
                    >
                      Search Project
                    </Button>
                  </div>
                </div>
                <div className="max-w-[250px] text-[11px] text-[#666]">
                  <div className="font-medium text-[#666]">Next up</div>
                  <ul className="mt-2 space-y-1.5 leading-5 text-[#333]">
                    <li>• Jump between projects without leaving the shell.</li>
                    <li>• Resume the last section from recent projects.</li>
                    <li>• Keep search available across the whole workspace.</li>
                  </ul>
                </div>
              </div>
            ) : null}
          </div>

          <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-5 py-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              AT A GLANCE
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Workspace Overview</div>
            <div className="mt-4 grid grid-cols-4 gap-3">
              <div>
                <div className="text-[18px] font-semibold leading-none text-[#1b2431]">
                  {projects.length}
                </div>
                <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
                  Active Projects
                </div>
              </div>
              <div>
                <div className="text-[18px] font-semibold leading-none text-[#1b2431]">
                  {preferences.pinnedSlugs.length}
                </div>
                <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
                  Pinned
                </div>
              </div>
              <div>
                <div className="text-[18px] font-semibold leading-none text-[#1b2431]">
                  {recentProjects.length}
                </div>
                <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
                  Recent
                </div>
              </div>
              <div>
                <div className="text-[18px] font-semibold leading-none text-[#d9534f]">
                  {countProjectsNeedingSetup(projects)}
                </div>
                <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
                  Need Setup
                </div>
              </div>
            </div>
            <div className="mt-5 text-[11px] text-[#7b8794]">
              Projects share one workspace search index.
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-5 py-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              QUICK ACCESS
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Pinned Projects</div>
            <div className="mt-3 space-y-2">
              {homePinnedProjects.length > 0 ? (
                homePinnedProjects.map((project) => (
                  <button
                    key={project.slug}
                    type="button"
                    className="flex w-full items-start justify-between gap-4 border-t border-[#e1e8ed] pt-3 text-left first:border-t-0 first:pt-0"
                    onClick={() => openProjectDashboard(project.slug)}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="h-4 w-[3px] rounded-full bg-[#22a5f1]" />
                        <span className="truncate text-[14px] font-semibold text-[#1b2431]">
                          {project.name}
                        </span>
                      </div>
                      <div className="mt-1 truncate pl-5 text-[11px] text-[#7b8794]">
                        {projectSummary(project)}
                      </div>
                    </div>
                    <span className="shrink-0 pt-0.5 text-[11px] text-[#666]">Open Dashboard</span>
                  </button>
                ))
              ) : (
                <div className="text-[12px] text-[#7b8794]">
                  Pin projects from the index below to keep them at the top of the workspace.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[4px] border border-[#e1e8ed] bg-white px-5 py-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              RESUME FLOW
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">Recent Projects</div>
            <div className="mt-3 space-y-2">
              {homeRecentProjects.length > 0 ? (
                homeRecentProjects.map(({ entry, project }) => (
                  <button
                    key={entry?.slug ?? project.slug}
                    type="button"
                    className="flex w-full items-start justify-between gap-4 border-t border-[#e1e8ed] pt-3 text-left first:border-t-0 first:pt-0"
                    onClick={() => {
                      if (entry) {
                        navigateToProjectTarget(navigate, buildResumeTarget(entry))
                        return
                      }
                      openProjectDashboard(project.slug)
                    }}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Clock3 className="size-3.5 text-[#22a5f1]" />
                        <span className="truncate text-[14px] font-semibold text-[#1b2431]">
                          {project.name}
                        </span>
                      </div>
                      <div className="mt-1 pl-5 text-[11px] text-[#7b8794]">
                        {entry ? describeProjectVisit(entry) : 'Open dashboard or switch into search'}
                      </div>
                    </div>
                    <span className="shrink-0 text-[11px] text-[#7b8794]">
                      {entry ? formatRelativeVisit(entry.visitedAt) : 'Ready'}
                    </span>
                  </button>
                ))
              ) : (
                <div className="text-[12px] text-[#7b8794]">
                  Recently visited projects appear here so users can reopen the same section.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="rounded-[4px] border border-[#e1e8ed] bg-white py-4">
          <div className="px-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              PROJECT INDEX
            </div>
            <div className="mt-1 text-[13px] font-semibold text-[#1b2431]">All Projects</div>
          </div>
          <div className="mt-4 grid grid-cols-[minmax(0,1fr)_120px_96px] gap-4 px-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#666]">
            <span>Project</span>
            <span>Updated</span>
            <span>State</span>
          </div>
          <div className="mt-2">
            {sortedProjects.map((project) => (
              <ProjectRow
                key={project.slug}
                project={project}
                pinned={isProjectPinned(project.slug, preferences)}
                onOpen={() => openProjectDashboard(project.slug)}
                onTogglePinned={() => togglePinnedProject(project.slug)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
