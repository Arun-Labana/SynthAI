import { motion } from 'framer-motion'
import { 
  Clock, 
  Loader2, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  GitPullRequest,
  Eye
} from 'lucide-react'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md' | 'lg'
}

const statusConfig: Record<string, {
  label: string
  icon: typeof Clock
  color: string
  bgColor: string
  animate?: boolean
}> = {
  pending: {
    label: 'Pending',
    icon: Clock,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-400/10',
  },
  pm_processing: {
    label: 'PM Agent',
    icon: Loader2,
    color: 'text-neon-cyan',
    bgColor: 'bg-neon-cyan/10',
    animate: true,
  },
  dev_processing: {
    label: 'Dev Agent',
    icon: Loader2,
    color: 'text-neon-purple',
    bgColor: 'bg-neon-purple/10',
    animate: true,
  },
  qa_processing: {
    label: 'QA Agent',
    icon: Loader2,
    color: 'text-neon-orange',
    bgColor: 'bg-neon-orange/10',
    animate: true,
  },
  sandbox_running: {
    label: 'Sandbox',
    icon: Loader2,
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-400/10',
    animate: true,
  },
  review_processing: {
    label: 'Reviewing',
    icon: Eye,
    color: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
    animate: true,
  },
  awaiting_approval: {
    label: 'Awaiting Approval',
    icon: AlertTriangle,
    color: 'text-neon-orange',
    bgColor: 'bg-neon-orange/10',
  },
  approved: {
    label: 'Approved',
    icon: CheckCircle,
    color: 'text-neon-green',
    bgColor: 'bg-neon-green/10',
  },
  rejected: {
    label: 'Rejected',
    icon: XCircle,
    color: 'text-neon-pink',
    bgColor: 'bg-neon-pink/10',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
  completed: {
    label: 'Completed',
    icon: GitPullRequest,
    color: 'text-neon-green',
    bgColor: 'bg-neon-green/10',
  },
}

const sizeClasses = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
  lg: 'px-4 py-2 text-base',
}

const iconSizes = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
}

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config = statusConfig[status] || {
    label: status,
    icon: Clock,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-400/10',
  }

  const Icon = config.icon

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full font-medium
        ${config.color} ${config.bgColor} ${sizeClasses[size]}
      `}
    >
      <Icon 
        className={`
          ${iconSizes[size]}
          ${config.animate ? 'animate-spin' : ''}
        `}
      />
      <span>{config.label}</span>
      {config.animate && (
        <motion.span
          className="w-1.5 h-1.5 rounded-full bg-current"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
    </span>
  )
}

