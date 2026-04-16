import { api } from '@/lib/api'

const STORAGE_PREFIX = 'datum:web-session:'

interface StoredWebSession {
  sessionId: string
}

function storageKey(projectSlug: string): string {
  return `${STORAGE_PREFIX}${projectSlug}`
}

function loadStoredSession(projectSlug: string): StoredWebSession | null {
  if (typeof window === 'undefined') return null
  const raw = window.sessionStorage.getItem(storageKey(projectSlug))
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as StoredWebSession
    if (parsed.sessionId) return parsed
  } catch {
    // Ignore invalid storage payloads and recreate the session.
  }
  window.sessionStorage.removeItem(storageKey(projectSlug))
  return null
}

function storeSession(projectSlug: string, sessionId: string): void {
  if (typeof window === 'undefined') return
  window.sessionStorage.setItem(storageKey(projectSlug), JSON.stringify({ sessionId }))
}

function clearSession(projectSlug: string): void {
  if (typeof window === 'undefined') return
  window.sessionStorage.removeItem(storageKey(projectSlug))
}

function buildSessionId(projectSlug: string): string {
  const suffix =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID().slice(0, 12)
      : `${Date.now()}`
  return `web-${projectSlug}-${suffix}`
}

async function startProjectSession(projectSlug: string): Promise<string> {
  const sessionId = buildSessionId(projectSlug)
  await api.lifecycle.start(sessionId, projectSlug, 'web')
  storeSession(projectSlug, sessionId)
  return sessionId
}

export async function ensureProjectWriteSession(projectSlug: string): Promise<string> {
  let sessionId = loadStoredSession(projectSlug)?.sessionId ?? null
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!sessionId) {
      sessionId = await startProjectSession(projectSlug)
    }
    try {
      await api.lifecycle.preflight(sessionId, 'get_project_context')
      return sessionId
    } catch (error) {
      clearSession(projectSlug)
      sessionId = null
      if (attempt === 1) throw error
    }
  }
  throw new Error('Unable to initialize web lifecycle session')
}
