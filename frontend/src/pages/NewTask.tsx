import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Sparkles, 
  FolderOpen, 
  ArrowRight, 
  Loader2,
  AlertCircle,
  Lightbulb
} from 'lucide-react'
import { useApi } from '../hooks/useApi'

const exampleTasks = [
  "Add a password reset feature with email verification to this FastAPI app",
  "Create a REST API endpoint for user profile management with CRUD operations",
  "Implement rate limiting middleware with Redis caching",
  "Add WebSocket support for real-time notifications",
  "Create a data export feature that generates CSV and JSON reports",
]

export default function NewTask() {
  const navigate = useNavigate()
  const { createTask, loading, error } = useApi()
  
  const [taskDescription, setTaskDescription] = useState('')
  const [repoPath, setRepoPath] = useState('')
  const [githubRepoUrl, setGithubRepoUrl] = useState('')
  const [customTaskId, setCustomTaskId] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!taskDescription.trim() || submitting) return
    
    setSubmitting(true)

    try {
      const result = await createTask(
        taskDescription,
        repoPath || undefined,
        githubRepoUrl || undefined,
        customTaskId || undefined
      )

      if (result?.task_id) {
        // Immediately navigate to watch progress
        navigate(`/tasks/${result.task_id}`)
      }
    } catch (err) {
      setSubmitting(false)
    }
  }

  const useExample = (example: string) => {
    setTaskDescription(example)
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-neon-cyan/20 to-neon-purple/20 border border-neon-cyan/30 mb-6">
          <Sparkles className="w-8 h-8 text-neon-cyan" />
        </div>
        <h1 className="text-3xl font-display font-bold text-white mb-3">
          Create New Task
        </h1>
        <p className="text-zinc-400 max-w-md mx-auto">
          Describe the feature you want to build. The AI agents will handle 
          specification, implementation, testing, and PR creation.
        </p>
      </motion.div>

      {/* Form */}
      <motion.form
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        {/* Task Description */}
        <div className="card">
          <label className="block text-sm font-medium text-white mb-3">
            What do you want to build?
          </label>
          <textarea
            value={taskDescription}
            onChange={(e) => setTaskDescription(e.target.value)}
            placeholder="Describe your feature in natural language..."
            rows={6}
            className="w-full px-4 py-3 rounded-lg bg-obsidian border border-white/10 text-white placeholder-zinc-500 focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan outline-none transition-all resize-none font-mono text-sm"
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-zinc-500">
              {taskDescription.length} characters
            </span>
          </div>
        </div>

        {/* Example Tasks */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-4 h-4 text-neon-orange" />
            <span className="text-sm font-medium text-white">Example Tasks</span>
          </div>
          <div className="space-y-2">
            {exampleTasks.map((example, i) => (
              <button
                key={i}
                type="button"
                onClick={() => useExample(example)}
                className="w-full text-left px-4 py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-transparent hover:border-neon-cyan/30 text-sm text-zinc-300 transition-all"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Advanced Options */}
        <div className="card">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors"
          >
            <FolderOpen className="w-4 h-4" />
            Advanced Options
            <span className={`transition-transform ${showAdvanced ? 'rotate-90' : ''}`}>
              →
            </span>
          </button>

          {showAdvanced && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-4 space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  GitHub Repository URL (for PR creation)
                </label>
                <input
                  type="text"
                  value={githubRepoUrl}
                  onChange={(e) => setGithubRepoUrl(e.target.value)}
                  placeholder="https://github.com/username/repo"
                  className="w-full px-4 py-3 rounded-lg bg-obsidian border border-white/10 text-white placeholder-zinc-500 focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan outline-none transition-all font-mono text-sm"
                />
                <p className="text-xs text-zinc-500 mt-1">
                  The AI will create a PR in this repository when approved
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Local Repository Path (for RAG context)
                </label>
                <input
                  type="text"
                  value={repoPath}
                  onChange={(e) => setRepoPath(e.target.value)}
                  placeholder="/path/to/your/repository"
                  className="w-full px-4 py-3 rounded-lg bg-obsidian border border-white/10 text-white placeholder-zinc-500 focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan outline-none transition-all font-mono text-sm"
                />
                <p className="text-xs text-zinc-500 mt-1">
                  Optional: Index existing code to give AI more context
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Custom Task ID
                </label>
                <input
                  type="text"
                  value={customTaskId}
                  onChange={(e) => setCustomTaskId(e.target.value)}
                  placeholder="my-feature-001"
                  className="w-full px-4 py-3 rounded-lg bg-obsidian border border-white/10 text-white placeholder-zinc-500 focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan outline-none transition-all font-mono text-sm"
                />
                <p className="text-xs text-zinc-500 mt-1">
                  Leave empty for auto-generated ID
                </p>
              </div>
            </motion.div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm">{error}</span>
          </motion.div>
        )}

        {/* Submit Button */}
        <motion.button
          type="submit"
          disabled={loading || !taskDescription.trim()}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full btn-primary flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Creating Task...
            </>
          ) : (
            <>
              Start AI Workflow
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </motion.button>

        <p className="text-center text-xs text-zinc-500">
          This will start the PM → Dev → QA → Review pipeline
        </p>
      </motion.form>
    </div>
  )
}

