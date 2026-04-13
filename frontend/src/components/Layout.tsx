import { useEffect, type ReactNode } from 'react'
import { Command, PanelRight, Search } from 'lucide-react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { useContextPanel } from '@/lib/context-panel'
import { toggleCommandPalette } from '@/components/CommandPalette'
import { Sidebar } from './Sidebar'

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { content, open, setOpen, toggleOpen } = useContextPanel()

  useEffect(() => {
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
        navigate({ to: '/search' })
      }

      if (event.key === 'Escape' && content && open) {
        setOpen(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [content, navigate, open, setOpen])

  const pathLabel =
    location.pathname === '/'
      ? 'Workspace'
      : location.pathname === '/search'
        ? 'Search'
        : location.pathname.startsWith('/projects/')
          ? 'Project'
          : 'Datum'

  return (
    <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(17,24,39,0.04),_transparent_38%),linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(244,244,245,0.92))] text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-border/80 bg-background/85 px-6 py-3 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
                {pathLabel}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                Filesystem-canonical workspace with routed dashboards, source-first editing,
                and durable search state.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => navigate({ to: '/search' })}
              >
                <Search />
                Search
                <kbd className="ml-1 rounded border px-1 py-0.5 text-[10px] text-muted-foreground">
                  /
                </kbd>
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={toggleCommandPalette}>
                <Command />
                Palette
                <kbd className="ml-1 rounded border px-1 py-0.5 text-[10px] text-muted-foreground">
                  Ctrl+K
                </kbd>
              </Button>
              {content && (
                <Button type="button" variant="outline" size="sm" onClick={toggleOpen}>
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
        <aside className="w-[22rem] shrink-0 border-l border-border/80 bg-card/86 backdrop-blur">
          {content}
        </aside>
      )}
    </div>
  )
}
