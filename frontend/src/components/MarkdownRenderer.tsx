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

import {
  extractHeadings,
  extractTechnicalTerms,
  slugifyHeading,
  stripFrontmatter,
  uniqueTechnicalTerms,
  type TechnicalTerm,
} from '@/lib/technical-terms'

interface MarkdownRendererProps {
  content: string
  projectSlug: string
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function renderHighlightedText(text: string, terms: TechnicalTerm[]): ReactNode[] {
  if (!text || terms.length === 0) {
    return [text]
  }

  const orderedTerms = terms
    .filter((term) => term.rawText.length >= 3)
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
        key={`${matchedTerm.termType}:${matchedTerm.rawText}:${index}`}
        to="/search"
        search={{ query: matchedTerm.rawText }}
        className="datum-entity rounded-sm border-b border-dashed border-amber-400/60 bg-amber-400/10 px-0.5 text-inherit transition-colors hover:bg-amber-400/20"
        title={`${matchedTerm.termType} · Search for ${matchedTerm.rawText}`}
      >
        {part}
      </Link>
    )
  })
}

function highlightNode(node: ReactNode, terms: TechnicalTerm[]): ReactNode {
  if (typeof node === 'string') {
    return renderHighlightedText(node, terms)
  }

  if (!isValidElement(node)) {
    return node
  }

  if (typeof node.type === 'string' && ['a', 'code', 'pre', 'svg'].includes(node.type)) {
    return node
  }

  const element = node as ReactElement<{ children?: ReactNode }>
  const children = Children.map(element.props.children, (child) =>
    highlightNode(child, terms),
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

export function MarkdownRenderer({ content, projectSlug }: MarkdownRendererProps) {
  const markdown = useMemo(() => stripFrontmatter(content), [content])
  const headings = useMemo(() => extractHeadings(markdown), [markdown])
  const technicalTerms = useMemo(
    () => uniqueTechnicalTerms(extractTechnicalTerms(markdown)),
    [markdown],
  )
  const headingIds = useMemo(
    () => new Map(headings.map((heading) => [heading.text, heading.id])),
    [headings],
  )

  return (
    <div className="datum-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          h1: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h1 id={id}>{highlightNode(children, technicalTerms)}</h1>
          },
          h2: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h2 id={id}>{highlightNode(children, technicalTerms)}</h2>
          },
          h3: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h3 id={id}>{highlightNode(children, technicalTerms)}</h3>
          },
          h4: ({ children }) => {
            const text = extractText(children)
            const id = headingIds.get(text) ?? slugifyHeading(text)
            return <h4 id={id}>{highlightNode(children, technicalTerms)}</h4>
          },
          p: ({ children }) => <p>{highlightNode(children, technicalTerms)}</p>,
          li: ({ children }) => <li>{highlightNode(children, technicalTerms)}</li>,
          blockquote: ({ children }) => <blockquote>{highlightNode(children, technicalTerms)}</blockquote>,
          td: ({ children }) => <td>{highlightNode(children, technicalTerms)}</td>,
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

      {technicalTerms.length > 0 && (
        <div className="mt-8 rounded-[1.5rem] border border-border/80 bg-card/50 p-4">
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            Linked entities
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {technicalTerms.map((term) => (
              <Link
                key={`${term.termType}:${term.rawText}`}
                to="/search"
                search={{ query: term.rawText, project: projectSlug }}
                className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs text-foreground transition-colors hover:bg-accent"
                title={`${term.termType} · Search for ${term.rawText}`}
              >
                <span>{term.rawText}</span>
                <span className="text-muted-foreground">{term.termType}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
