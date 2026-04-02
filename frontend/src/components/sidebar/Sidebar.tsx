import { NavLink } from 'react-router-dom'
import {
  Mic2, Library, UserPlus, BookOpen, Clock, Box,
  Settings, AudioWaveform, FileText, ArrowRightLeft,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', icon: Mic2, label: 'Studio' },
  { to: '/voices', icon: Library, label: 'Voices' },
  { to: '/clone', icon: UserPlus, label: 'Clone' },
  { to: '/projects', icon: BookOpen, label: 'Audiobooks' },
  { to: '/speech-to-text', icon: FileText, label: 'STT' },
  { to: '/speech-to-speech', icon: ArrowRightLeft, label: 'Voice Swap' },
  { to: '/history', icon: Clock, label: 'History' },
  { to: '/models', icon: Box, label: 'Models' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="flex flex-col h-full w-[60px] bg-zinc-900/50 border-r border-zinc-800/50">
      {/* Logo */}
      <div className="flex items-center justify-center h-14 border-b border-zinc-800/50">
        <img
          src="/logo.png"
          alt="FrenzAI"
          className="w-8 h-8 object-contain"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
            e.currentTarget.nextElementSibling?.classList.remove('hidden')
          }}
        />
        <AudioWaveform className="w-6 h-6 text-violet-500 hidden" />
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col items-center py-2 gap-1 overflow-y-auto">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `group relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-violet-500/15 text-violet-400'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div className="absolute left-0 w-[3px] h-5 bg-violet-500 rounded-r-full" />
                )}
                <Icon className="w-[18px] h-[18px]" />
                {/* Tooltip */}
                <div className="absolute left-full ml-2 px-2.5 py-1 bg-zinc-800 border border-zinc-700 rounded-lg text-xs text-zinc-200 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg">
                  {label}
                </div>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
