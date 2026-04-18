import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { ExternalLink, FolderPlus, Pin, PinOff, Search } from 'lucide-react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import type { Project } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useProjectCreation } from '@/lib/project-creation'
import {
  buildProjectSwitchTarget,
  describeProjectVisit,
  navigateToProjectTarget,
} from '@/lib/project-navigation'
import {
  isProjectPinned,
  togglePinnedProject,
  useProjectPreferences,
} from '@/lib/project-preferences'
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
  pinned,
  onSelect,
  onTogglePinned,
}: {
  project: Project
  subtitle: string
  pinned: boolean
  onSelect: () => void
  onTogglePinned: () => void
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-t border-[#e1e8ed] px-5 py-3 first:border-t-0 hover:bg-[rgba(34,165,241,0.04)]">
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onSelect}>
        <div className="truncate text-[14px] font-semibold text-[#1b2431]">{project.name}</div>
        <div className="truncate text-[11px] text-[#7b8794]">{subtitle}</div>
      </button>
      <button
        type="button"
        className="mt-0.5 text-[#999] transition hover:text-[#22a5f1]"
        aria-label={pinned ? `Unpin ${project.name}` : `Pin ${project.name}`}
        onClick={onTogglePinned}
      >
        {pinned ? <Pin className="size-3.5 fill-current" /> : <PinOff className="size-3.5" />}
      </button>
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

  return (
    <div
      className="fixed inset-0 z-50 bg-[rgba(27,36,49,0.5)]"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="absolute left-[240px] top-[52px] w-[420px] rounded-[4px] border border-[#e1e8ed] bg-white shadow-[0px_8px_30px_0px_rgba(0,0,0,0.25)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-[#e1e8ed] px-5 py-4">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
            Switch Project
          </div>
          <div className="mt-1 flex items-center justify-between gap-3">
            <div className="text-[20px] font-semibold text-[#1b2431]">{selectedProject}</div>
            <ExternalLink className="size-4 text-[#999]" />
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-[4px] border border-[#d6e0e8] px-3 py-2">
            <Search className="size-3.5 text-[#999]" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="project, slug, or recent…"
              className="w-full border-0 bg-transparent p-0 text-[13px] text-[#333] outline-none placeholder:text-[#999]"
            />
          </div>
        </div>

        <div className="max-h-[420px] overflow-auto py-2">
          {pinnedProjects.length > 0 && (
            <div>
              <div className="px-5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
                Pinned
              </div>
              {pinnedProjects.map((project) => (
                <ProjectOption
                  key={`pinned:${project.slug}`}
                  project={project}
                  subtitle={project.description || 'Pinned project'}
                  pinned
                  onSelect={() => selectProject(project.slug)}
                  onTogglePinned={() => togglePinnedProject(project.slug)}
                />
              ))}
            </div>
          )}

          {recentProjects.length > 0 && (
            <div>
              <div className="px-5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
                Recent
              </div>
              {recentProjects.map(({ entry, project }) => (
                <ProjectOption
                  key={`recent:${project.slug}`}
                  project={project}
                  subtitle={describeProjectVisit(entry)}
                  pinned={isProjectPinned(project.slug, preferences)}
                  onSelect={() => selectProject(project.slug)}
                  onTogglePinned={() => togglePinnedProject(project.slug)}
                />
              ))}
            </div>
          )}

          <div>
            <div className="px-5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#7b8794]">
              All Projects
            </div>
            {filteredProjects.map((project) => (
              <ProjectOption
                key={`all:${project.slug}`}
                project={project}
                subtitle={project.description || project.slug}
                pinned={isProjectPinned(project.slug, preferences)}
                onSelect={() => selectProject(project.slug)}
                onTogglePinned={() => togglePinnedProject(project.slug)}
              />
            ))}
            {filteredProjects.length === 0 && (
              <div className="px-5 py-4 text-[12px] text-[#7b8794]">No projects match that filter.</div>
            )}
          </div>
        </div>

        <div className="border-t border-[#e1e8ed] px-5 py-4">
          <Button
            type="button"
            variant="outline"
            className="w-full justify-center gap-2 border-[#d6e0e8] bg-white text-[#1b2431]"
            onClick={() => {
              onOpenChange(false)
              openCreateProjectDialog({ source: 'project-switcher' })
            }}
          >
            <FolderPlus className="size-4" />
            Create Project
          </Button>
        </div>
      </div>
    </div>
  )
}
