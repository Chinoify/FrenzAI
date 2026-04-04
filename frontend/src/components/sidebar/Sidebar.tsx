import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Mic2, Library, UserPlus, BookOpen, Clock, Box,
  Settings, AudioWaveform, FileText, ArrowRightLeft,
  ChevronLeft, ChevronRight,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', icon: Mic2, label: 'Text to Speech' },
  { to: '/voices', icon: Library, label: 'Voice Library' },
  { to: '/clone', icon: UserPlus, label: 'Add Voices' },
  { to: '/projects', icon: BookOpen, label: 'Audiobooks' },
  { to: '/speech-to-text', icon: FileText, label: 'Speech to Text' },
  { to: '/speech-to-speech', icon: ArrowRightLeft, label: 'Voice Swap' },
  { to: '/history', icon: Clock, label: 'History' },
  { to: '/models', icon: Box, label: 'AI Models' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const [expanded, setExpanded] = useState(true)

  return (
    <aside className={`flex flex-col h-full bg-zinc-900/50 border-r border-zinc-800/50 transition-all duration-300 ${expanded ? 'w-[220px]' : 'w-[60px]'}`}>
      {/* Logo */}
      <div className="flex items-center h-14 border-b border-zinc-800/50 px-3 gap-2">
        <img
          src="/logo.png"
          alt="FrenzAI"
          className="w-8 h-8 object-contain shrink-0"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
            e.currentTarget.nextElementSibling?.classList.remove('hidden')
          }}
        />
        <AudioWaveform className="w-6 h-6 text-violet-500 hidden shrink-0" />
        {expanded && <span className="text-sm font-bold text-zinc-200 truncate">FrenzAI</span>}
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-auto p-1 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300"
        >
          {expanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col py-2 gap-0.5 overflow-y-auto px-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl transition-all duration-200 ${
                expanded ? 'px-3 py-2.5' : 'justify-center px-0 py-2.5'
              } ${
                isActive
                  ? 'bg-violet-500/15 text-violet-400 font-medium'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div className="absolute left-0 w-[3px] h-5 bg-violet-500 rounded-r-full" />
                )}
                <Icon className={`shrink-0 ${expanded ? 'w-[18px] h-[18px]' : 'w-5 h-5'}`} />
                {expanded && <span className="text-sm truncate">{label}</span>}
                {!expanded && (
                  <div className="absolute left-full ml-2 px-2.5 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-200 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg">
                    {label}
                  </div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {expanded && (
        <div className="px-3 py-3 border-t border-zinc-800/50">
          <p className="text-[10px] text-zinc-600 text-center">FrenzAI v1.0</p>
        </div>
      )}
    </aside>
  )
}
