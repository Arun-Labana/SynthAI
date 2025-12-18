import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Plus, 
  ArrowRight, 
  Activity, 
  CheckCircle2, 
  Clock,
  AlertCircle,
  Bot,
  Server,
  GitBranch
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import StatusBadge from '../components/StatusBadge'

interface Task {
  task_id: string
  status: string
  description: string
}

interface HealthStatus {
  api: string
  docker: string
  github: string
}

export default function Dashboard() {
  const { getTasks, checkHealth, loading } = useApi()
  const [tasks, setTasks] = useState<Task[]>([])
  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000) // Refresh every 10s
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    const [tasksRes, healthRes] = await Promise.all([
      getTasks(),
      checkHealth(),
    ])
    
    if (tasksRes) {
      setTasks(tasksRes.tasks)
    }
    if (healthRes) {
      setHealth(healthRes)
    }
  }

  const stats = {
    total: tasks.length,
    running: tasks.filter(t => 
      ['pm_processing', 'dev_processing', 'qa_processing', 'sandbox_running', 'review_processing'].includes(t.status)
    ).length,
    completed: tasks.filter(t => t.status === 'completed').length,
    pending: tasks.filter(t => t.status === 'awaiting_approval').length,
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white mb-2">
            Dashboard
          </h1>
          <p className="text-zinc-400">
            Monitor your AI development tasks
          </p>
        </div>
        <Link to="/tasks/new" className="btn-primary flex items-center gap-2">
          <Plus className="w-5 h-5" />
          New Task
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Tasks', value: stats.total, icon: Bot, color: 'text-white' },
          { label: 'Running', value: stats.running, icon: Activity, color: 'text-neon-cyan' },
          { label: 'Awaiting Approval', value: stats.pending, icon: Clock, color: 'text-neon-orange' },
          { label: 'Completed', value: stats.completed, icon: CheckCircle2, color: 'text-neon-green' },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="card"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-zinc-400 text-sm">{stat.label}</span>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <span className={`text-3xl font-bold ${stat.color}`}>
              {stat.value}
            </span>
          </motion.div>
        ))}
      </div>

      {/* System Health */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="card"
      >
        <h2 className="text-lg font-semibold text-white mb-4">System Health</h2>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'API Server', status: health?.api, icon: Server },
            { label: 'Docker', status: health?.docker, icon: Bot },
            { label: 'GitHub', status: health?.github, icon: GitBranch },
          ].map((item) => (
            <div
              key={item.label}
              className="flex items-center gap-3 p-3 rounded-lg bg-white/5"
            >
              <item.icon className="w-5 h-5 text-zinc-400" />
              <div>
                <p className="text-sm text-white">{item.label}</p>
                <p className={`text-xs ${
                  item.status === 'healthy' || item.status === 'connected' 
                    ? 'text-neon-green' 
                    : item.status?.includes('error') || item.status?.includes('unavailable')
                      ? 'text-neon-pink'
                      : 'text-zinc-500'
                }`}>
                  {item.status || 'Unknown'}
                </p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Task List */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="card"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Recent Tasks</h2>
          {loading && (
            <span className="text-xs text-zinc-500">Refreshing...</span>
          )}
        </div>

        {tasks.length === 0 ? (
          <div className="text-center py-12">
            <Bot className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
            <h3 className="text-lg font-medium text-zinc-400 mb-2">
              No tasks yet
            </h3>
            <p className="text-zinc-500 mb-6">
              Create your first task to get started
            </p>
            <Link to="/tasks/new" className="btn-secondary inline-flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Create Task
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task, i) => (
              <motion.div
                key={task.task_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  to={`/tasks/${task.task_id}`}
                  className="flex items-center gap-4 p-4 rounded-lg bg-white/5 hover:bg-white/10 border border-transparent hover:border-neon-cyan/30 transition-all group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="font-mono text-sm text-neon-cyan">
                        #{task.task_id}
                      </span>
                      <StatusBadge status={task.status} size="sm" />
                    </div>
                    <p className="text-white truncate">
                      {task.description || 'No description'}
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-zinc-500 group-hover:text-neon-cyan transition-colors" />
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  )
}

