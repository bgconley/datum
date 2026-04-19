import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'datum.project-preferences.v1'
const CHANGE_EVENT = 'datum:project-preferences-change'
const MAX_RECENT_PROJECTS = 8

export type ProjectVisitSection =
  | 'dashboard'
  | 'inbox'
  | 'sessions'
  | 'settings'
  | 'search'
  | 'document'
  | 'unknown'

export interface ProjectVisitSnapshot {
  slug: string
  pathname: string
  searchStr: string
  section: ProjectVisitSection
  visitedAt: string
}

export interface ProjectPreferences {
  recent: ProjectVisitSnapshot[]
  pinnedSlugs: string[]
  lastOpenedSlug: string | null
}

const DEFAULT_PREFERENCES: ProjectPreferences = {
  recent: [],
  pinnedSlugs: [],
  lastOpenedSlug: null,
}

let cachedRawPreferences: string | null = null
let cachedPreferences: ProjectPreferences = DEFAULT_PREFERENCES

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizePreferences(value: unknown): ProjectPreferences {
  if (!value || typeof value !== 'object') {
    return DEFAULT_PREFERENCES
  }

  const prefs = value as Partial<ProjectPreferences>
  const recent = Array.isArray(prefs.recent)
    ? prefs.recent.filter(
        (entry): entry is ProjectVisitSnapshot =>
          Boolean(entry) &&
          typeof entry === 'object' &&
          typeof entry.slug === 'string' &&
          typeof entry.pathname === 'string' &&
          typeof entry.searchStr === 'string' &&
          typeof entry.section === 'string' &&
          typeof entry.visitedAt === 'string',
      )
    : []

  const pinnedSlugs = Array.isArray(prefs.pinnedSlugs)
    ? prefs.pinnedSlugs.filter((slug): slug is string => typeof slug === 'string')
    : []

  return {
    recent,
    pinnedSlugs,
    lastOpenedSlug: typeof prefs.lastOpenedSlug === 'string' ? prefs.lastOpenedSlug : null,
  }
}

export function readProjectPreferences(): ProjectPreferences {
  if (!canUseStorage()) {
    return DEFAULT_PREFERENCES
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    cachedRawPreferences = null
    cachedPreferences = DEFAULT_PREFERENCES
    return DEFAULT_PREFERENCES
  }

  if (raw === cachedRawPreferences) {
    return cachedPreferences
  }

  try {
    cachedRawPreferences = raw
    cachedPreferences = normalizePreferences(JSON.parse(raw))
    return cachedPreferences
  } catch {
    cachedRawPreferences = null
    cachedPreferences = DEFAULT_PREFERENCES
    return DEFAULT_PREFERENCES
  }
}

function writeProjectPreferences(next: ProjectPreferences) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT))
}

export function subscribeProjectPreferences(listener: () => void) {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handler = () => listener()
  window.addEventListener(CHANGE_EVENT, handler)
  window.addEventListener('storage', handler)
  return () => {
    window.removeEventListener(CHANGE_EVENT, handler)
    window.removeEventListener('storage', handler)
  }
}

export function useProjectPreferences() {
  return useSyncExternalStore(
    subscribeProjectPreferences,
    readProjectPreferences,
    () => DEFAULT_PREFERENCES,
  )
}

export function recordProjectVisit(snapshot: ProjectVisitSnapshot) {
  const current = readProjectPreferences()
  const nextRecent = [
    snapshot,
    ...current.recent.filter((entry) => entry.slug !== snapshot.slug),
  ].slice(0, MAX_RECENT_PROJECTS)

  writeProjectPreferences({
    ...current,
    recent: nextRecent,
    lastOpenedSlug: snapshot.slug,
  })
}

export function togglePinnedProject(slug: string) {
  const current = readProjectPreferences()
  const isPinned = current.pinnedSlugs.includes(slug)
  const pinnedSlugs = isPinned
    ? current.pinnedSlugs.filter((item) => item !== slug)
    : [...current.pinnedSlugs, slug]

  writeProjectPreferences({
    ...current,
    pinnedSlugs,
  })
}

export function setLastOpenedProject(slug: string | null) {
  const current = readProjectPreferences()
  writeProjectPreferences({
    ...current,
    lastOpenedSlug: slug,
  })
}

export function isProjectPinned(slug: string, preferences: ProjectPreferences) {
  return preferences.pinnedSlugs.includes(slug)
}
