import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Highlight, themes } from 'prism-react-renderer'
import { ChevronDown, ChevronRight, File, Copy, Check } from 'lucide-react'

interface CodeViewerProps {
  files: Record<string, string>
  title?: string
}

export default function CodeViewer({ files, title = 'Generated Code' }: CodeViewerProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(
    new Set(Object.keys(files).slice(0, 1)) // Expand first file by default
  )
  const [copiedFile, setCopiedFile] = useState<string | null>(null)

  const fileList = Object.entries(files)

  const toggleFile = (filename: string) => {
    const newExpanded = new Set(expandedFiles)
    if (newExpanded.has(filename)) {
      newExpanded.delete(filename)
    } else {
      newExpanded.add(filename)
    }
    setExpandedFiles(newExpanded)
  }

  const copyCode = async (filename: string, code: string) => {
    await navigator.clipboard.writeText(code)
    setCopiedFile(filename)
    setTimeout(() => setCopiedFile(null), 2000)
  }

  const getLanguage = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase()
    const langMap: Record<string, string> = {
      py: 'python',
      js: 'javascript',
      ts: 'typescript',
      tsx: 'tsx',
      jsx: 'jsx',
      json: 'json',
      md: 'markdown',
      yaml: 'yaml',
      yml: 'yaml',
    }
    return langMap[ext || ''] || 'python'
  }

  if (fileList.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
        <div className="text-zinc-500 text-center py-8">
          No files generated yet
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      
      <div className="space-y-2">
        {fileList.map(([filename, code]) => {
          const isExpanded = expandedFiles.has(filename)
          const language = getLanguage(filename)
          
          return (
            <div
              key={filename}
              className="border border-white/10 rounded-lg overflow-hidden"
            >
              {/* File header */}
              <button
                onClick={() => toggleFile(filename)}
                className="w-full flex items-center gap-2 px-4 py-3 bg-obsidian hover:bg-white/5 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-zinc-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-zinc-400" />
                )}
                <File className="w-4 h-4 text-neon-cyan" />
                <span className="font-mono text-sm text-white">{filename}</span>
                <span className="ml-auto text-xs text-zinc-500">
                  {code.split('\n').length} lines
                </span>
              </button>

              {/* Code content */}
              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="relative">
                      {/* Copy button */}
                      <button
                        onClick={() => copyCode(filename, code)}
                        className="absolute top-2 right-2 p-2 rounded bg-white/10 hover:bg-white/20 transition-colors z-10"
                        title="Copy code"
                      >
                        {copiedFile === filename ? (
                          <Check className="w-4 h-4 text-neon-green" />
                        ) : (
                          <Copy className="w-4 h-4 text-zinc-400" />
                        )}
                      </button>

                      {/* Syntax highlighted code */}
                      <Highlight
                        theme={themes.nightOwl}
                        code={code}
                        language={language}
                      >
                        {({ style, tokens, getLineProps, getTokenProps }) => (
                          <pre
                            className="p-4 overflow-x-auto text-sm font-mono"
                            style={{ ...style, background: 'rgba(0,0,0,0.4)' }}
                          >
                            {tokens.map((line, i) => (
                              <div key={i} {...getLineProps({ line })}>
                                <span className="inline-block w-8 text-zinc-600 select-none">
                                  {i + 1}
                                </span>
                                {line.map((token, key) => (
                                  <span key={key} {...getTokenProps({ token })} />
                                ))}
                              </div>
                            ))}
                          </pre>
                        )}
                      </Highlight>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </div>
    </div>
  )
}

