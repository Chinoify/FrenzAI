import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

interface ToastProps {
  message: string
  type?: 'success' | 'error' | 'info'
  onClose: () => void
  duration?: number
}

export default function Toast({ message, type = 'info', onClose, duration = 4000 }: ToastProps) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false)
      setTimeout(onClose, 200)
    }, duration)
    return () => clearTimeout(timer)
  }, [duration, onClose])

  const icons = { success: CheckCircle, error: AlertCircle, info: Info }
  const colors = {
    success: 'border-green-500 text-green-400',
    error: 'border-red-500 text-red-400',
    info: 'border-violet-500 text-violet-400',
  }
  const Icon = icons[type]

  return (
    <div
      className={`fixed bottom-12 right-4 flex items-center gap-2 px-4 py-2 bg-zinc-800 border rounded-lg shadow-lg z-50 transition-opacity duration-200 ${
        colors[type]
      } ${visible ? 'opacity-100' : 'opacity-0'}`}
    >
      <Icon className="w-4 h-4 flex-shrink-0" />
      <span className="text-sm text-zinc-200">{message}</span>
      <button onClick={onClose} className="ml-2 text-zinc-500 hover:text-zinc-300">
        <X className="w-3 h-3" />
      </button>
    </div>
  )
}
