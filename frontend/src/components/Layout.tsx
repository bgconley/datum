import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { PanelRight, Search, Settings } from 'lucide-react'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'

import { useContextPanel } from '@/lib/context-panel'
import { toggleCommandPalette } from '@/components/CommandPalette'
import { Sidebar } from './Sidebar'

export interface LayoutConfig {
  sidebarWidth: number
  contextPanelWidth: number
}

const defaultLayoutConfig: LayoutConfig = {
  sidebarWidth: 220,
  contextPanelWidth: 300,
}

const LayoutConfigContext = createContext<LayoutConfig>(defaultLayoutConfig)

export function useLayoutConfig() {
  return useContext(LayoutConfigContext)
}

export function LayoutConfigProvider({
  config,
  children,
}: {
  config: Partial<LayoutConfig>
  children: ReactNode
}) {
  const merged = { ...defaultLayoutConfig, ...config }
  return (
    <LayoutConfigContext.Provider value={merged}>{children}</LayoutConfigContext.Provider>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { content, open, setOpen, toggleOpen } = useContextPanel()
  const layoutConfig = useLayoutConfig()

  useEffect(() => {
    const focusSearch = () => {
      window.dispatchEvent(new CustomEvent('datum:focus-search'))
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const tagName = target?.tagName ?? ''
      const isEditable =
        target?.isContentEditable ||
        ['INPUT', 'TEXTAREA', 'SELECT'].includes(tagName)

      if (
        event.key === '/' &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !isEditable
      ) {
        event.preventDefault()
        if (location.pathname === '/search') {
          focusSearch()
          return
        }
        navigate({ to: '/search' })
        window.setTimeout(focusSearch, 0)
      }

      if (
        event.key.toLowerCase() === 'e' &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !isEditable &&
        location.pathname.includes('/docs/')
      ) {
        event.preventDefault()
        window.dispatchEvent(new CustomEvent('datum:enter-edit-mode'))
      }

      if (event.key === 'Escape' && content && open) {
        setOpen(false)
        return
      }

      if (event.key === 'Escape' && location.pathname.includes('/docs/')) {
        window.dispatchEvent(new CustomEvent('datum:exit-edit-mode'))
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [content, location.pathname, navigate, open, setOpen])

  const selectedProject = location.pathname.startsWith('/projects/')
    ? decodeURIComponent(location.pathname.split('/')[2] ?? '')
    : null

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      {/* Header — 48px dark bar matching Figma NX 01 */}
      <header className="flex h-[48px] shrink-0 items-center justify-between bg-sidebar px-4">
        <div className="flex items-center gap-4">
          <span className="text-[14px] font-bold text-white">DATUM</span>
          <div className="h-6 w-px bg-white/20" />
          {selectedProject ? (
            <Link
              to="/projects/$slug"
              params={{ slug: selectedProject }}
              className="text-[13px] text-primary"
            >
              {selectedProject} ▾
            </Link>
          ) : (
            <span className="text-[13px] text-white/60">No project</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-white">
          <button
            type="button"
            className="text-[14px] hover:text-white/80"
            onClick={() => {
              if (location.pathname === '/search') {
                window.dispatchEvent(new CustomEvent('datum:focus-search'))
                return
              }
              navigate({ to: '/search' })
              window.setTimeout(() => {
                window.dispatchEvent(new CustomEvent('datum:focus-search'))
              }, 0)
            }}
          >
            <Search className="size-4" />
          </button>
          <button
            type="button"
            className="text-[14px] hover:text-white/80"
            onClick={toggleCommandPalette}
          >
            <Settings className="size-4" />
          </button>
          {content && (
            <button
              type="button"
              className="text-[14px] hover:text-white/80"
              onClick={toggleOpen}
            >
              <PanelRight className="size-4" />
            </button>
          )}
          <span className="text-[12px]">admin ▾</span>
        </div>
      </header>
      {/* Body — sidebar + main + context panel */}
      <div className="flex min-h-0 flex-1">
        <Sidebar style={{ width: layoutConfig.sidebarWidth }} />
        <main className="min-w-0 flex-1 overflow-auto">{children}</main>
        {content && open && (
          <aside
            className="shrink-0 overflow-auto border-l border-border bg-white"
            style={{ width: layoutConfig.contextPanelWidth }}
          >
            {content}
          </aside>
        )}
      </div>
    </div>
  )
}
