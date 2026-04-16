import { useEffect, useRef, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Project } from '@/lib/api'
import type { SearchDraft, SearchMode } from '@/lib/search-route'

interface SearchBarProps {
  value: SearchDraft
  projects: Project[]
  loading?: boolean
  onChange: (next: SearchDraft) => void
  onSearch: () => void | Promise<void>
  onReset: () => void
}

const selectClassName =
  'h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

const SEARCH_MODES: Array<{ value: SearchMode; label: string }> = [
  { value: 'find_docs', label: 'Find docs' },
  { value: 'ask_question', label: 'Ask question' },
  { value: 'find_decisions', label: 'Find decisions' },
  { value: 'search_history', label: 'Search history' },
  { value: 'compare_over_time', label: 'Compare over time' },
]

const placeholders: Record<SearchMode, string> = {
  find_docs: 'Search documents, APIs, env vars, and design notes',
  ask_question: 'Ask a grounded question, e.g. What changed in auth flow?',
  find_decisions: 'Find the ADR or decision that settled a topic',
  search_history: 'Search how a document or concept evolved over time',
  compare_over_time: 'Search a timestamped cabinet state to compare decisions over time',
}

export function SearchBar({
  value,
  projects,
  loading = false,
  onChange,
  onSearch,
  onReset,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const handleFocusSearch = () => {
      inputRef.current?.focus()
      inputRef.current?.select()
    }

    window.addEventListener('datum:focus-search', handleFocusSearch)
    return () => window.removeEventListener('datum:focus-search', handleFocusSearch)
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!value.query.trim()) {
      return
    }
    await onSearch()
  }

  return (
    <form onSubmit={handleSubmit} className="rounded border border-border bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {SEARCH_MODES.map((mode) => (
            <Button
              key={mode.value}
              type="button"
              size="xs"
              variant={value.mode === mode.value ? 'default' : 'outline'}
              onClick={() => onChange({ ...value, mode: mode.value })}
            >
              {mode.label}
            </Button>
          ))}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            ref={inputRef}
            value={value.query}
            onChange={(event) => onChange({ ...value, query: event.target.value })}
            placeholder={placeholders[value.mode]}
            className="flex-1"
            autoFocus
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={loading || !value.query.trim()}>
              {loading ? 'Searching...' : 'Search'}
            </Button>
            <Button type="button" variant="outline" onClick={onReset} disabled={loading}>
              Reset
            </Button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Project
            </span>
            <select
              value={value.project}
              onChange={(event) => onChange({ ...value, project: event.target.value })}
              className={selectClassName}
            >
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.slug} value={project.slug}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Version Scope
            </span>
            <select
              value={value.versionMode}
              onChange={(event) =>
                onChange({
                  ...value,
                  versionMode: event.target.value as SearchDraft['versionMode'],
                })
              }
              className={selectClassName}
            >
              <option value="current">Current only</option>
              <option value="all">All versions</option>
              <option value="as_of">As of timestamp</option>
              <option value="snapshot">Named snapshot</option>
              <option value="branch">Branch head</option>
            </select>
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              As Of
            </span>
            <Input
              type="datetime-local"
              value={value.asOf}
              onChange={(event) => onChange({ ...value, asOf: event.target.value })}
              disabled={value.versionMode !== 'as_of'}
            />
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Snapshot
            </span>
            <Input
              value={value.snapshot}
              onChange={(event) => onChange({ ...value, snapshot: event.target.value })}
              disabled={value.versionMode !== 'snapshot'}
              placeholder="approved-v1"
            />
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Branch
            </span>
            <Input
              value={value.branch}
              onChange={(event) => onChange({ ...value, branch: event.target.value })}
              disabled={value.versionMode !== 'branch'}
              placeholder="main"
            />
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Result Limit
            </span>
            <select
              value={value.limit}
              onChange={(event) =>
                onChange({
                  ...value,
                  limit: Number(event.target.value),
                })
              }
              className={selectClassName}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </label>
        </div>

        <div className="text-xs leading-5 text-muted-foreground">
          Search modes shape the retrieval task without hiding the underlying cabinet scope. Use current/all for day-to-day retrieval, as-of for temporal reconstruction, snapshot for named release states, and branch for head-set lookup outside main.
        </div>
      </div>
    </form>
  )
}
