import { createContext, useContext, useState, type ReactNode } from 'react'

interface ContextPanelState {
  content: ReactNode | null
  open: boolean
  setContent: (content: ReactNode | null) => void
  setOpen: (open: boolean) => void
  toggleOpen: () => void
}

const ContextPanelContext = createContext<ContextPanelState>({
  content: null,
  open: true,
  setContent: () => {},
  setOpen: () => {},
  toggleOpen: () => {},
})

export function ContextPanelProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null)
  const [open, setOpen] = useState(true)

  return (
    <ContextPanelContext.Provider
      value={{
        content,
        open,
        setContent,
        setOpen,
        toggleOpen: () => setOpen((current) => !current),
      }}
    >
      {children}
    </ContextPanelContext.Provider>
  )
}

export function useContextPanel() {
  return useContext(ContextPanelContext)
}
