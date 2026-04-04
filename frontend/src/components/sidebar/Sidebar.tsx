import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Mic2, Library, UserPlus, BookOpen, Clock, Box,
  Settings, AudioWaveform, FileText, ArrowRightLeft,
  ChevronLeft, ChevronRight,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', icon: Mic2, label: 'Text to Speech', shortLabel: 'Studio' },
  { to: '/voices', icon: Library, label: 'Voice Library', shortLabel: 'Voices' },
  { to: '/clone', icon: UserPlus, label: 'Add Voices', shortLabel: 'Clone' },
  { to: '/projects', icon: BookOpen, label: 'Audiobooks', shortLabel: 'Books' },
  { to: '/speech-to-text', icon: FileText, label: 'Speech to Text', shortLabel: 'STT' },
  { to: '/speech-to-speech', icon: ArrowRightLeft, label: 'Voice Swap', shortLabel: 'Swap' },
  { to: '/history', icon: Clock, label: 'History', shortLabel: 'History' },
  { to: '/models', icon: Box, label: 'AI Models', shortLabel: 'Models' },
  { to: '/settings', icon: Settings, label: 'Settings', shortLabel: 'Settings' },
]

export default function Sidebar() {
  const [expanded, setExpanded] = useState(true)

  return (
    <aside className={`flex flex-col h-full bg-white border-r border-slate-200 transition-all duration-300 ${expanded ? 'w-[220px]' : 'w-[60px]'}`}>
      {/* Logo + collapse toggle */}
      <div className="flex items-center h-14 border-b border-slate-200 px-3 gap-2">
        <img
          src="/logo.png"
          alt="FrenzAI"
          className="w-8 h-8 object-contain shrink-0"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
            e.currentTarget.nextElementSibling?.classList.remove('hidden')
          }}
        />
        <AudioWaveform className="w-6 h-6 text-violet-600 hidden shrink-0" />
        {expanded && <span className="text-sm font-bold text-slate-800 truncate">FrenzAI</span>}
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-auto p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
        >
          {expanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col py-2 gap-0.5 overflow-y-auto px-2">
        {NAV_ITEMS.map(({ to, icon: Icon, label, shortLabel }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl transition-all duration-200 ${
                expanded ? 'px-3 py-2.5' : 'justify-center px-0 py-2.5'
              } ${
                isActive
                  ? 'bg-violet-50 text-violet-700 font-medium'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div className="absolute left-0 w-[3px] h-5 bg-violet-500 rounded-r-full" />
                )}
                <Icon className={`shrink-0 ${expanded ? 'w-[18px] h-[18px]' : 'w-5 h-5'}`} />
                {expanded && (
                  <span className="text-sm truncate">{label}</span>
                )}
                {/* Tooltip when collapsed */}
                {!expanded && (
                  <div className="absolute left-full ml-2 px-2.5 py-1.5 bg-slate-800 text-white rounded-lg text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg">
                    {label}
                  </div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      {expanded && (
        <div className="px-3 py-3 border-t border-slate-200">
          <p className="text-[10px] text-slate-400 text-center">FrenzAI v1.0</p>
        </div>
      )}
    </aside>
  )
}
