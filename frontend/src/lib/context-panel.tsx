import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

interface ContextPanelValue {
  content: ReactNode | null
  open: boolean
}

interface ContextPanelActions {
  setContent: (content: ReactNode | null) => void
  setOpen: (open: boolean) => void
  toggleOpen: () => void
}

const ContextPanelStateContext = createContext<ContextPanelValue>({
  content: null,
  open: true,
})

const ContextPanelActionsContext = createContext<ContextPanelActions>({
  setContent: () => {},
  setOpen: () => {},
  toggleOpen: () => {},
})

export function ContextPanelProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null)
  const [open, setOpen] = useState(true)
  const toggleOpen = useCallback(() => setOpen((current) => !current), [])
  const stateValue = useMemo(() => ({ content, open }), [content, open])
  const actionsValue = useMemo(
    () => ({
      setContent,
      setOpen,
      toggleOpen,
    }),
    [toggleOpen],
  )

  return (
    <ContextPanelActionsContext.Provider value={actionsValue}>
      <ContextPanelStateContext.Provider value={stateValue}>
        {children}
      </ContextPanelStateContext.Provider>
    </ContextPanelActionsContext.Provider>
  )
}

export function useContextPanel() {
  return useContext(ContextPanelActionsContext)
}

export function useContextPanelState() {
  return useContext(ContextPanelStateContext)
}
