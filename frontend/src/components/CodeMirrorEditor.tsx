import CodeMirror from '@uiw/react-codemirror'
import { keymap } from '@codemirror/view'
import { EditorView } from '@codemirror/view'
import { markdown } from '@codemirror/lang-markdown'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { sql } from '@codemirror/lang-sql'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
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
      theme={oneDark}
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
