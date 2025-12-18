import { motion } from 'framer-motion'
import { Bot, CheckCircle, AlertCircle, Clock, Loader2 } from 'lucide-react'

interface Message {
  agent: string
  content: string
  timestamp: string
}

interface AgentTimelineProps {
  messages: Message[]
  currentStatus: string
}

const agentColors: Record<string, string> = {
  'PM Agent': 'text-neon-cyan border-neon-cyan',
  'Dev Agent': 'text-neon-purple border-neon-purple',
  'QA Agent': 'text-neon-orange border-neon-orange',
  'Sandbox': 'text-yellow-400 border-yellow-400',
  'Reviewer Agent': 'text-blue-400 border-blue-400',
  'GitHub': 'text-neon-green border-neon-green',
  'System': 'text-zinc-400 border-zinc-400',
}

const agentIcons: Record<string, string> = {
  'PM Agent': '📋',
  'Dev Agent': '💻',
  'QA Agent': '🧪',
  'Sandbox': '📦',
  'Reviewer Agent': '👁️',
  'GitHub': '🔗',
  'System': '⚙️',
}

// Pipeline stages for visualization
const pipelineStages = [
  { id: 'pm', name: 'PM Agent', icon: '📋', status: 'pm_processing' },
  { id: 'dev', name: 'Dev Agent', icon: '💻', status: 'dev_processing' },
  { id: 'qa', name: 'QA Agent', icon: '🧪', status: 'qa_processing' },
  { id: 'sandbox', name: 'Sandbox', icon: '📦', status: 'sandbox_running' },
  { id: 'review', name: 'Reviewer', icon: '👁️', status: 'review_processing' },
  { id: 'approval', name: 'Approval', icon: '✅', status: 'awaiting_approval' },
]

function PipelineVisualization({ currentStatus }: { currentStatus: string }) {
  const getStageState = (stage: typeof pipelineStages[0], index: number) => {
    const statusOrder = ['pending', 'pm_processing', 'dev_processing', 'qa_processing', 'sandbox_running', 'review_processing', 'awaiting_approval', 'approved', 'completed']
    const currentIndex = statusOrder.indexOf(currentStatus)
    const stageIndex = statusOrder.indexOf(stage.status)
    
    if (currentStatus === stage.status) return 'active'
    if (currentIndex > stageIndex) return 'completed'
    return 'pending'
  }

  return (
    <div className="mb-6 p-4 rounded-lg bg-obsidian border border-white/10">
      <div className="flex items-center justify-between">
        {pipelineStages.map((stage, index) => {
          const state = getStageState(stage, index)
          return (
            <div key={stage.id} className="flex items-center">
              <div className="flex flex-col items-center">
                <motion.div
                  className={`
                    w-10 h-10 rounded-full flex items-center justify-center text-lg
                    ${state === 'active' ? 'bg-neon-cyan/20 border-2 border-neon-cyan' : ''}
                    ${state === 'completed' ? 'bg-neon-green/20 border-2 border-neon-green' : ''}
                    ${state === 'pending' ? 'bg-white/5 border-2 border-white/20' : ''}
                  `}
                  animate={state === 'active' ? { scale: [1, 1.1, 1] } : {}}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  {state === 'active' ? (
                    <Loader2 className="w-5 h-5 text-neon-cyan animate-spin" />
                  ) : state === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-neon-green" />
                  ) : (
                    <span className="opacity-50">{stage.icon}</span>
                  )}
                </motion.div>
                <span className={`text-xs mt-1 ${state === 'active' ? 'text-neon-cyan' : state === 'completed' ? 'text-neon-green' : 'text-zinc-500'}`}>
                  {stage.name}
                </span>
              </div>
              {index < pipelineStages.length - 1 && (
                <div className={`w-8 h-0.5 mx-1 ${state === 'completed' ? 'bg-neon-green' : 'bg-white/10'}`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function AgentTimeline({ messages, currentStatus }: AgentTimelineProps) {
  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return timestamp
    }
  }

  const isRunning = [
    'pm_processing',
    'dev_processing',
    'qa_processing',
    'sandbox_running',
    'review_processing',
  ].includes(currentStatus)

  return (
    <div className="card">
      {/* Pipeline Visualization */}
      <PipelineVisualization currentStatus={currentStatus} />
      
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">Agent Activity</h3>
        {isRunning && (
          <span className="flex items-center gap-2 text-sm text-neon-cyan">
            <motion.span
              className="w-2 h-2 rounded-full bg-neon-cyan"
              animate={{ scale: [1, 1.2, 1], opacity: [1, 0.5, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            Processing...
          </span>
        )}
      </div>

      {messages.length === 0 ? (
        <div className="text-center py-8 text-zinc-500">
          <Loader2 className="w-12 h-12 mx-auto mb-3 opacity-50 animate-spin text-neon-cyan" />
          <p className="text-neon-cyan">Agents are working...</p>
          <p className="text-xs mt-2">This may take a minute while the AI processes your request</p>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map((message, index) => {
            const colorClass = agentColors[message.agent] || 'text-zinc-400 border-zinc-400'
            const icon = agentIcons[message.agent] || '🤖'
            
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex gap-4"
              >
                {/* Timeline line */}
                <div className="flex flex-col items-center">
                  <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center bg-obsidian ${colorClass}`}>
                    <span className="text-sm">{icon}</span>
                  </div>
                  {index < messages.length - 1 && (
                    <div className="w-0.5 h-full min-h-[20px] bg-white/10 mt-2" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`font-semibold ${colorClass.split(' ')[0]}`}>
                      {message.agent}
                    </span>
                    <span className="text-xs text-zinc-500">
                      {formatTime(message.timestamp)}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-300 leading-relaxed">
                    {message.content}
                  </p>
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}

