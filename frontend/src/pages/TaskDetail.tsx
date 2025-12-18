import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  ArrowLeft, 
  ExternalLink, 
  CheckCircle, 
  XCircle,
  RefreshCw,
  FileCode,
  TestTube,
  Loader2
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useWebSocket } from '../hooks/useWebSocket'
import StatusBadge from '../components/StatusBadge'
import AgentTimeline from '../components/AgentTimeline'
import CodeViewer from '../components/CodeViewer'

interface Message {
  agent: string
  content: string
  timestamp: string
}

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const { getTask, getTaskCode, getTaskSpec, approveTask, rejectTask, loading } = useApi()
  
  const [task, setTask] = useState<{
    task_id: string
    status: string
    iteration_count: number
    is_tests_passing: boolean
    is_approved: boolean
    pr_url: string | null
    error_message: string | null
    messages: Message[]
    code_files: string[]
    test_files: string[]
  } | null>(null)
  
  const [codeFiles, setCodeFiles] = useState<Record<string, string>>({})
  const [testFiles, setTestFiles] = useState<Record<string, string>>({})
  const [spec, setSpec] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'code' | 'tests' | 'spec'>('timeline')
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)

  // WebSocket for real-time updates
  const { lastMessage, isConnected } = useWebSocket(taskId || null, {
    onMessage: (msg) => {
      if (msg.type === 'status_update') {
        loadTask()
      }
    },
  })

  useEffect(() => {
    if (taskId) {
      loadTask()
    }
  }, [taskId])

  // Auto-refresh while task is processing
  useEffect(() => {
    if (!task) return
    
    const processingStatuses = [
      'pending',
      'pm_processing',
      'dev_processing',
      'qa_processing',
      'sandbox_running',
      'review_processing',
    ]
    
    if (processingStatuses.includes(task.status)) {
      const interval = setInterval(() => {
        loadTask()
      }, 3000) // Poll every 3 seconds
      
      return () => clearInterval(interval)
    }
  }, [task?.status])

  useEffect(() => {
    // Load code when tab changes
    if (activeTab === 'code' && Object.keys(codeFiles).length === 0) {
      loadCode()
    }
    if (activeTab === 'spec' && !spec) {
      loadSpec()
    }
  }, [activeTab])

  const loadTask = async () => {
    if (!taskId) return
    const result = await getTask(taskId)
    if (result) {
      setTask(result)
    }
  }

  const loadCode = async () => {
    if (!taskId) return
    const result = await getTaskCode(taskId)
    if (result) {
      setCodeFiles(result.code_files || {})
      setTestFiles(result.test_files || {})
    }
  }

  const loadSpec = async () => {
    if (!taskId) return
    const result = await getTaskSpec(taskId)
    if (result?.specification) {
      setSpec(result.specification)
    }
  }

  const handleApprove = async () => {
    if (!taskId) return
    setApproving(true)
    await approveTask(taskId)
    await loadTask()
    setApproving(false)
  }

  const handleReject = async () => {
    if (!taskId) return
    setRejecting(true)
    await rejectTask(taskId, 'Rejected by user')
    await loadTask()
    setRejecting(false)
  }

  if (!task) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-neon-cyan animate-spin" />
      </div>
    )
  }

  const canApprove = task.status === 'awaiting_approval'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-zinc-400" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-display font-bold text-white">
                Task #{task.task_id}
              </h1>
              <StatusBadge status={task.status} />
              {isConnected && (
                <span className="flex items-center gap-1 text-xs text-neon-green">
                  <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
                  Live
                </span>
              )}
            </div>
            <p className="text-sm text-zinc-400 mt-1">
              Iteration {task.iteration_count} • {task.messages.length} messages
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadTask}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <RefreshCw className={`w-5 h-5 text-zinc-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
          
          {task.pr_url && (
            <a
              href={task.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary flex items-center gap-2"
            >
              <ExternalLink className="w-4 h-4" />
              View PR
            </a>
          )}
        </div>
      </div>

      {/* Approval Actions */}
      {canApprove && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card bg-gradient-to-r from-neon-orange/10 to-transparent border-neon-orange/30"
        >
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">
                Review Required
              </h3>
              <p className="text-sm text-zinc-400">
                The AI has completed the implementation. Review the code and approve to create a PR.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleReject}
                disabled={rejecting}
                className="px-4 py-2 rounded-lg border border-neon-pink/50 text-neon-pink hover:bg-neon-pink/10 transition-colors flex items-center gap-2"
              >
                {rejecting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <XCircle className="w-4 h-4" />
                )}
                Reject
              </button>
              <button
                onClick={handleApprove}
                disabled={approving}
                className="btn-primary flex items-center gap-2"
              >
                {approving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle className="w-4 h-4" />
                )}
                Approve & Create PR
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Error Display */}
      {task.error_message && (
        <div className="card bg-red-500/10 border-red-500/30">
          <p className="text-red-400">{task.error_message}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 pb-2">
        {[
          { id: 'timeline', label: 'Activity', icon: RefreshCw },
          { id: 'code', label: 'Code', icon: FileCode, count: task.code_files.length },
          { id: 'tests', label: 'Tests', icon: TestTube, count: task.test_files.length },
          { id: 'spec', label: 'Specification', icon: FileCode },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg transition-all
              ${activeTab === tab.id
                ? 'bg-neon-cyan/10 text-neon-cyan border border-neon-cyan/30'
                : 'text-zinc-400 hover:text-white hover:bg-white/5'
              }
            `}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="px-1.5 py-0.5 rounded text-xs bg-white/10">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'timeline' && (
          <AgentTimeline 
            messages={task.messages} 
            currentStatus={task.status}
          />
        )}

        {activeTab === 'code' && (
          <CodeViewer files={codeFiles} title="Implementation Code" />
        )}

        {activeTab === 'tests' && (
          <CodeViewer files={testFiles} title="Test Files" />
        )}

        {activeTab === 'spec' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4">
              Technical Specification
            </h3>
            {spec ? (
              <div className="prose prose-invert prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-mono bg-obsidian p-4 rounded-lg">
                  {spec}
                </pre>
              </div>
            ) : (
              <p className="text-zinc-500">No specification available yet.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

