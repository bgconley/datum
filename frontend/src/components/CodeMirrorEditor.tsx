import CodeMirror from '@uiw/react-codemirror'
import { keymap } from '@codemirror/view'
import { EditorView } from '@codemirror/view'
import { markdown } from '@codemirror/lang-markdown'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { sql } from '@codemirror/lang-sql'
import { yaml } from '@codemirror/lang-yaml'
import { githubLight } from '@uiw/codemirror-theme-github'
import type { Extension } from '@codemirror/state'

type EditorLanguage =
  | 'markdown'
  | 'json'
  | 'sql'
  | 'yaml'
  | 'typescript'
  | 'javascript'
  | 'toml'
  | 'prisma'
  | 'text'

interface CodeMirrorEditorProps {
  value: string
  onChange: (value: string) => void
  onSave?: () => void
  language?: EditorLanguage
  readOnly?: boolean
  className?: string
}

function languageExtension(language: CodeMirrorEditorProps['language']): Extension {
  switch (language) {
    case 'json':
      return json()
    case 'sql':
      return sql()
    case 'typescript':
      return javascript({ typescript: true })
    case 'javascript':
      return javascript()
    case 'markdown':
      return markdown()
    case 'yaml':
      return yaml()
    case 'toml':
    case 'prisma':
    case 'text':
    default:
      return []
  }
}

const datumEditorTheme = EditorView.theme({
  '&': {
    fontSize: '12.5px',
    lineHeight: '1.55',
    color: '#333333',
    backgroundColor: '#ffffff',
  },
  '.cm-scroller': {
    fontFamily: '"Fira Code", "SFMono-Regular", ui-monospace, monospace',
  },
  '.cm-gutters': {
    backgroundColor: '#f8fbfd',
    color: '#94a3b8',
    borderRight: '1px solid #e1e8ed',
  },
  '.cm-content': {
    paddingTop: '14px',
    paddingBottom: '14px',
  },
  '.cm-line': {
    paddingLeft: '10px',
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(34, 165, 241, 0.06)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'rgba(34, 165, 241, 0.06)',
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: 'rgba(34, 165, 241, 0.18)',
  },
})

export function CodeMirrorEditor({
  value,
  onChange,
  onSave,
  language = 'markdown',
  readOnly = false,
  className,
}: CodeMirrorEditorProps) {
  return (
    <CodeMirror
      value={value}
      height="100%"
      minHeight="28rem"
      theme={githubLight}
      readOnly={readOnly}
      editable={!readOnly}
      className={className}
      basicSetup={{
        foldGutter: true,
        highlightActiveLine: true,
        highlightActiveLineGutter: true,
        lineNumbers: true,
      }}
      extensions={[
        languageExtension(language),
        EditorView.lineWrapping,
        datumEditorTheme,
        keymap.of([
          {
            key: 'Mod-s',
            run: () => {
              onSave?.()
              return true
            },
          },
        ]),
      ]}
      onChange={onChange}
    />
  )
}
