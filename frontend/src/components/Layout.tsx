import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { Command, PanelRight, Search } from 'lucide-react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
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

  const pathLabel =
    location.pathname === '/'
      ? 'Workspace'
      : location.pathname === '/search'
        ? 'Search'
        : location.pathname.startsWith('/projects/')
          ? 'Project'
          : 'Datum'

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar style={{ width: layoutConfig.sidebarWidth }} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-sidebar-border bg-sidebar px-6 py-3 text-sidebar-foreground">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-sidebar-foreground/60">
                {pathLabel}
              </div>
              <div className="mt-1 text-sm text-sidebar-foreground/60">
                Filesystem-canonical workspace with routed dashboards, source-first editing,
                and durable search state.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-accent/80"
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
                <Search />
                Search
                <kbd className="ml-1 rounded border border-sidebar-border px-1 py-0.5 text-[10px] text-sidebar-foreground/60">
                  /
                </kbd>
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-accent/80"
                onClick={toggleCommandPalette}
              >
                <Command />
                Palette
                <kbd className="ml-1 rounded border border-sidebar-border px-1 py-0.5 text-[10px] text-sidebar-foreground/60">
                  Ctrl+K
                </kbd>
              </Button>
              {content && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-accent/80"
                  onClick={toggleOpen}
                >
                  <PanelRight />
                  {open ? 'Hide panel' : 'Show panel'}
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
      {content && open && (
        <aside
          className="shrink-0 border-l border-border bg-white"
          style={{ width: layoutConfig.contextPanelWidth }}
        >
          {content}
        </aside>
      )}
    </div>
  )
}
