import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '../components/sidebar/Sidebar'
import { useAppStore } from '../stores/appStore'

export default function AppLayout() {
  const { fetchHealth, fetchModels } = useAppStore()

  useEffect(() => {
    fetchHealth()
    fetchModels()
    const interval = setInterval(fetchHealth, 15000)
    return () => clearInterval(interval)
  }, [fetchHealth, fetchModels])

  return (
    <div className="flex h-screen bg-zinc-950">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="px-8 py-6 max-w-[1400px] mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
