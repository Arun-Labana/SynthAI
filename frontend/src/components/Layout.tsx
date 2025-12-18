import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  LayoutDashboard, 
  PlusCircle, 
  GitBranch, 
  Bot,
  Cpu
} from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/tasks/new', icon: PlusCircle, label: 'New Task' },
  ]

  return (
    <div className="min-h-screen bg-void bg-grid-pattern">
      {/* Ambient background effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-neon-cyan/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-neon-purple/5 rounded-full blur-3xl" />
      </div>

      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 glass border-r border-white/10 z-50">
        <div className="p-6">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 mb-10">
            <div className="relative">
              <Bot className="w-10 h-10 text-neon-cyan" />
              <Cpu className="w-5 h-5 text-neon-purple absolute -bottom-1 -right-1" />
            </div>
            <div>
              <h1 className="font-display font-bold text-lg text-white">
                SynthAI
              </h1>
              <p className="text-xs text-zinc-500">Code Synthesis</p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`
                    flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300
                    ${isActive 
                      ? 'bg-neon-cyan/10 text-neon-cyan border border-neon-cyan/30' 
                      : 'text-zinc-400 hover:text-white hover:bg-white/5'
                    }
                  `}
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="activeNav"
                      className="absolute left-0 w-1 h-8 bg-neon-cyan rounded-r"
                    />
                  )}
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <GitBranch className="w-4 h-4" />
            <span>v0.1.0</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 min-h-screen">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="p-8"
        >
          {children}
        </motion.div>
      </main>
    </div>
  )
}

