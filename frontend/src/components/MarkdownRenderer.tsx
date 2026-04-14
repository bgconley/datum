import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react'
import { Link } from '@tanstack/react-router'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

import type { DocumentEntityMention } from '@/lib/api'
import {
  extractHeadings,
  slugifyHeading,
  stripFrontmatter,
} from '@/lib/technical-terms'

interface MarkdownRendererProps {
  content: string
  projectSlug: string
  entityMentions?: DocumentEntityMention[]
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

interface HighlightTerm {
  rawText: string
  title: string
  key: string
  entityId: string
  entityType: string
  canonicalName: string
}

function renderHighlightedText(
  text: string,
  terms: HighlightTerm[],
  projectSlug: string,
): ReactNode[] {
  if (!text || terms.length === 0) {
    return [text]
  }

  const orderedTerms = terms
    .filter((term) => term.rawText.length >= 2)
    .sort((left, right) => right.rawText.length - left.rawText.length)

  if (orderedTerms.length === 0) {
    return [text]
  }

  const pattern = new RegExp(
    `(${orderedTerms.map((term) => escapeRegExp(term.rawText)).join('|')})`,
    'g',
  )
  const parts = text.split(pattern)
  return parts.filter(Boolean).map((part, index) => {
    const matchedTerm = orderedTerms.find((term) => term.rawText === part)
    if (!matchedTerm) {
      return part
    }

    return (
      <Link
        key={`${matchedTerm.key}:${index}`}
        to="/projects/$slug/entities/$entityId"
        params={{ slug: projectSlug, entityId: matchedTerm.entityId }}
        className="datum-entity rounded-sm border-b border-dashed border-amber-400/60 bg-amber-400/10 px-0.5 text-inherit transition-colors hover:bg-amber-400/20"
        title={matchedTerm.title}
      >
        {part}
      </Link>
    )
  })
}

function highlightNode(
  node: ReactNode,
  terms: HighlightTerm[],
  projectSlug: string,
): ReactNode {
  if (typeof node === 'string') {
    return renderHighlightedText(node, terms, projectSlug)
  }

  if (!isValidElement(node)) {
    return node
  }

  if (typeof node.type === 'string' && ['a', 'code', 'pre', 'svg'].includes(node.type)) {
    return node
  }

  const element = node as ReactElement<{ children?: ReactNode }>
  const children = Children.map(element.props.children, (child) =>
    highlightNode(child, terms, projectSlug),
  )
  return cloneElement(element, undefined, children)
}

function extractText(children: ReactNode): string {
  if (typeof children === 'string') {
    return children
  }
  if (Array.isArray(children)) {
    return children.map(extractText).join('')
  }
  if (isValidElement(children)) {
    const element = children as ReactElement<{ children?: ReactNode }>
    return extractText(element.props.children)
  }
  return ''
}

function MermaidBlock({ chart }: { chart: string }) {
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const id = useId().replace(/:/g, '-')

  useEffect(() => {
    let active = true

    const renderChart = async () => {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'strict',
        })
        const { svg: nextSvg } = await mermaid.render(`datum-mermaid-${id}`, chart)
        if (active) {
          setSvg(nextSvg)
          setError(null)
        }
      } catch (nextError) {
        if (active) {
          setError(nextError instanceof Error ? nextError.message : String(nextError))
        }
      }
    }

    void renderChart()
    return () => {
      active = false
    }
  }, [chart, id])

  if (error) {
    return (
      <div className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Mermaid render failed: {error}
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card/60 px-4 py-6 text-sm text-muted-foreground">
        Rendering Mermaid diagram…
      </div>
    )
  }

  return (
    <div
      className="overflow-auto rounded-2xl border border-border/70 bg-slate-950/90 p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

export function MarkdownRenderer({
  content,
  projectSlug,
  entityMentions = [],
}: MarkdownRendererProps) {
  const markdown = useMemo(() => stripFrontmatter(content), [content])
  const headings = useMemo(() => extractHeadings(markdown), [markdown])
  const headingIds = useMemo(
    () => new Map(headings.map((heading) => [heading.text, heading.id])),
    [headings],
  )
  const highlightTerms = useMemo<HighlightTerm[]>(() => {
    const seen = new Set<string>()
    return entityMentions
      .filter((mention) => mention.raw_text.trim())
      .filter((mention) => {
        const key = `${mention.entity_id}:${mention.raw_text}`
        if (seen.has(key)) {
          return false
        }
        seen.add(key)
        return true
      })
      .map((mention) => ({
        rawText: mention.raw_text,
        title: `${mention.entity_type} · ${mention.canonical_name}`,
        key: `${mention.entity_id}:${mention.raw_text}`,
        entityId: mention.entity_id,
        entityType: mention.entity_type,
        canonicalName: mention.canonical_name,
      }))
  }, [entityMentions])

  return (
    <div className="datum-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          h1: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h1 id={id}>{highlightNode(children, highlightTerms, projectSlug)}</h1>
          },
          h2: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h2 id={id}>{highlightNode(children, highlightTerms, projectSlug)}</h2>
          },
          h3: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h3 id={id}>{highlightNode(children, highlightTerms, projectSlug)}</h3>
          },
          h4: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h4 id={id}>{highlightNode(children, highlightTerms, projectSlug)}</h4>
          },
          p: ({ children }) => <p>{highlightNode(children, highlightTerms, projectSlug)}</p>,
          li: ({ children }) => <li>{highlightNode(children, highlightTerms, projectSlug)}</li>,
          blockquote: ({ children }) => (
            <blockquote>{highlightNode(children, highlightTerms, projectSlug)}</blockquote>
          ),
          td: ({ children }) => <td>{highlightNode(children, highlightTerms, projectSlug)}</td>,
          code(props) {
            const { children, className } = props
            const match = /language-(\w+)/.exec(className || '')
            const language = match?.[1]
            const code = String(children).replace(/\n$/, '')

            if (language === 'mermaid') {
              return <MermaidBlock chart={code} />
            }

            return (
              <code className={className}>
                {children}
              </code>
            )
          },
          a: ({ href, children }) => {
            if (!href) {
              return <span>{children}</span>
            }
            if (href.startsWith('#')) {
              return (
                <a href={href} className="text-amber-300 underline decoration-amber-400/40 underline-offset-4">
                  {children}
                </a>
              )
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-amber-300 underline decoration-amber-400/40 underline-offset-4"
              >
                {children}
              </a>
            )
          },
        }}
      >
        {markdown}
      </ReactMarkdown>

      {highlightTerms.length > 0 && (
        <div className="mt-8 rounded-[1.5rem] border border-border/80 bg-card/50 p-4">
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Linked entities
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {highlightTerms.map((mention) => (
              <Link
                key={mention.key}
                to="/projects/$slug/entities/$entityId"
                params={{ slug: projectSlug, entityId: mention.entityId }}
                className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-foreground transition-colors hover:bg-accent"
                title={mention.title}
              >
                <span>{mention.canonicalName}</span>
                <span className="text-muted-foreground">{mention.entityType}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
