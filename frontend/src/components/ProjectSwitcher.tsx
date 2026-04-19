import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import type { Project } from '@/lib/api'
import { useProjectCreation } from '@/lib/project-creation'
import {
  buildProjectSwitchTarget,
  describeProjectVisit,
  navigateToProjectTarget,
} from '@/lib/project-navigation'
import { useProjectPreferences } from '@/lib/project-preferences'
import { useProjectsQuery } from '@/lib/workspace-query'

function matchesProject(project: Project, query: string) {
  const normalized = query.trim().toLowerCase()
  if (!normalized) {
    return true
  }

  return (
    project.name.toLowerCase().includes(normalized) ||
    project.slug.toLowerCase().includes(normalized) ||
    (project.description ?? '').toLowerCase().includes(normalized)
  )
}

function ProjectOption({
  project,
  subtitle,
  meta,
  onSelect,
}: {
  project: Project
  subtitle: string
  meta?: string
  onSelect: () => void
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-[#e1e8ed] px-4 py-3 first:border-t-0 hover:bg-[rgba(34,165,241,0.04)]">
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onSelect}>
        <div className="flex items-center gap-2">
          <div className="h-4 w-[3px] shrink-0 rounded-full bg-[#22a5f1]" />
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold text-[#1b2431]">{project.name}</div>
            <div className="truncate text-[10px] text-[#7b8794]">{subtitle}</div>
          </div>
        </div>
      </button>
      {meta ? <span className="shrink-0 pt-0.5 text-[10px] text-[#666]">{meta}</span> : null}
    </div>
  )
}

export function ProjectSwitcher({
  open,
  onOpenChange,
  selectedProject,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedProject: string
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const { openCreateProjectDialog } = useProjectCreation()
  const projectsQuery = useProjectsQuery()
  const preferences = useProjectPreferences()
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const projects = projectsQuery.data ?? []

  useEffect(() => {
    if (!open) {
      setQuery('')
      return
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onOpenChange, open])

  const projectBySlug = useMemo(
    () => new Map(projects.map((project) => [project.slug, project])),
    [projects],
  )

  const filteredProjects = useMemo(
    () => projects.filter((project) => matchesProject(project, deferredQuery)),
    [deferredQuery, projects],
  )

  const pinnedProjects = useMemo(
    () =>
      preferences.pinnedSlugs
        .map((slug) => projectBySlug.get(slug))
        .filter((project): project is Project => Boolean(project))
        .filter((project) => matchesProject(project, deferredQuery)),
    [deferredQuery, preferences.pinnedSlugs, projectBySlug],
  )

  const recentProjects = useMemo(
    () =>
      preferences.recent
        .map((entry) => {
          const project = projectBySlug.get(entry.slug)
          if (!project || !matchesProject(project, deferredQuery)) {
            return null
          }
          return { entry, project }
        })
        .filter(
          (item): item is { entry: (typeof preferences.recent)[number]; project: Project } =>
            Boolean(item),
        ),
    [deferredQuery, preferences.recent, projectBySlug],
  )

  const selectProject = (slug: string) => {
    navigateToProjectTarget(
      navigate,
      buildProjectSwitchTarget(location.pathname, location.searchStr, slug),
    )
    onOpenChange(false)
  }

  if (!open) {
    return null
  }

  const showMatches = deferredQuery.trim().length > 0

  return (
    <div
      className="fixed inset-0 z-50 bg-[rgba(27,36,49,0.5)]"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="absolute left-[155px] top-[34px] w-[300px] rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_30px_0px_rgba(0,0,0,0.25)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-[#e1e8ed] px-4 py-4">
          <div className="flex items-center gap-2 rounded-[4px] border border-[#d6e0e8] bg-white px-3 py-2">
            <Search className="size-3.5 text-[#999]" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects..."
              className="w-full border-0 bg-transparent p-0 text-[12px] text-[#333] outline-none placeholder:text-[#999]"
            />
          </div>
        </div>

        <div className="max-h-[360px] overflow-auto py-1">
          {!showMatches && pinnedProjects.length > 0 && (
            <div>
              <div className="px-4 pb-1 pt-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
                Pinned
              </div>
              {pinnedProjects.map((project) => (
                <ProjectOption
                  key={`pinned:${project.slug}`}
                  project={project}
                  subtitle={project.description || `${project.slug} • ${project.status.toLowerCase()}`}
                  meta={project.slug === selectedProject ? 'Current' : 'Open'}
                  onSelect={() => selectProject(project.slug)}
                />
              ))}
            </div>
          )}

          {!showMatches && recentProjects.length > 0 && (
            <div>
              <div className="px-4 pb-1 pt-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
                Recent
              </div>
              {recentProjects.map(({ entry, project }) => (
                <ProjectOption
                  key={`recent:${project.slug}`}
                  project={project}
                  subtitle={describeProjectVisit(entry)}
                  meta={new Date(entry.visitedAt).toLocaleDateString() === new Date().toLocaleDateString() ? 'Today' : undefined}
                  onSelect={() => selectProject(project.slug)}
                />
              ))}
            </div>
          )}

          <div>
            <div className="px-4 pb-1 pt-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              {showMatches ? 'Projects' : 'Actions'}
            </div>
            {showMatches ? (
              filteredProjects.length > 0 ? (
                filteredProjects.map((project) => (
                  <ProjectOption
                    key={`all:${project.slug}`}
                    project={project}
                    subtitle={project.description || project.slug}
                    meta={project.slug === selectedProject ? 'Current' : undefined}
                    onSelect={() => selectProject(project.slug)}
                  />
                ))
              ) : (
                <div className="px-4 py-4 text-[12px] text-[#7b8794]">No projects match that filter.</div>
              )
            ) : (
              <>
                <button
                  type="button"
                  className="mx-4 mt-1 flex w-[calc(100%-2rem)] items-center rounded-[3px] bg-[#22a5f1] px-3 py-[8px] text-left text-[12px] font-medium text-white"
                  onClick={() => {
                    onOpenChange(false)
                    openCreateProjectDialog({ source: 'project-switcher' })
                  }}
                >
                  Create Project
                </button>
                <div className="border-t border-[#e1e8ed] px-4 py-[10px] text-[10px] text-[#7b8794]">
                  Switching preserves dashboard, inbox, sessions, and search.
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
