import { create } from 'zustand'
import type { Chapter, ProjectDetail } from '../types'
import { apiFetch, apiUpload, BACKEND_URL } from '../lib/api'

interface KokoroVoice {
  code: string
  name: string
  language: string
  gender: string
}

interface ProjectState {
  projects: ProjectDetail[]
  currentProject: ProjectDetail | null
  loading: boolean
  generating: boolean
  generationProgress: { chapter: number; total: number; title: string; status: string } | null
  kokoroVoices: KokoroVoice[]

  fetchProjects: () => Promise<void>
  fetchProject: (id: string) => Promise<void>
  uploadBook: (file: File, name: string, model?: string) => Promise<ProjectDetail>
  createFromText: (name: string, text: string) => Promise<ProjectDetail>
  updateChapter: (projectId: string, chapterId: string, updates: Partial<Chapter>) => Promise<void>
  createChapter: (projectId: string, title: string, text: string, index?: number) => Promise<void>
  deleteChapter: (projectId: string, chapterId: string) => Promise<void>
  generateChapter: (projectId: string, chapterId: string) => Promise<void>
  generateAll: (projectId: string, voiceId?: string, model?: string) => Promise<void>
  mergeExport: (projectId: string, format: string, acxCompliant?: boolean) => Promise<string>
  exportChaptersACX: (projectId: string) => Promise<any>
  deleteProject: (id: string) => Promise<void>
  fetchKokoroVoices: () => Promise<void>
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  generating: false,
  generationProgress: null,
  kokoroVoices: [],

  fetchProjects: async () => {
    set({ loading: true })
    try {
      const projects = await apiFetch<ProjectDetail[]>('/projects')
      set({ projects })
    } catch {
      // ignore
    } finally {
      set({ loading: false })
    }
  },

  fetchProject: async (id) => {
    set({ loading: true })
    try {
      const project = await apiFetch<ProjectDetail>(`/projects/${id}`)
      set({ currentProject: project })
    } catch {
      // ignore
    } finally {
      set({ loading: false })
    }
  },

  uploadBook: async (file, name, model) => {
    const form = new FormData()
    form.append('file', file)
    form.append('name', name || file.name.replace(/\.[^.]+$/, ''))
    if (model) form.append('default_model', model)
    const project = await apiUpload<ProjectDetail>('/projects/upload', form)
    set((s) => ({ projects: [project, ...s.projects], currentProject: project }))
    return project
  },

  createFromText: async (name, text) => {
    const project = await apiFetch<ProjectDetail>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, text }),
    })
    set((s) => ({ projects: [project, ...s.projects], currentProject: project }))
    return project
  },

  updateChapter: async (projectId, chapterId, updates) => {
    const chapter = await apiFetch<Chapter>(`/projects/${projectId}/chapters/${chapterId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
    set((s) => {
      if (!s.currentProject) return s
      const chapters = s.currentProject.chapters.map((ch) =>
        ch.id === chapterId ? chapter : ch
      )
      return { currentProject: { ...s.currentProject, chapters } }
    })
  },

  createChapter: async (projectId, title, text, index) => {
    const chapter = await apiFetch<Chapter>(`/projects/${projectId}/chapters`, {
      method: 'POST',
      body: JSON.stringify({ title, text, index }),
    })
    // Refetch to get correct indices
    await get().fetchProject(projectId)
  },

  deleteChapter: async (projectId, chapterId) => {
    await apiFetch(`/projects/${projectId}/chapters/${chapterId}`, { method: 'DELETE' })
    await get().fetchProject(projectId)
  },

  generateChapter: async (projectId, chapterId) => {
    const chapter = await apiFetch<Chapter>(
      `/projects/${projectId}/chapters/${chapterId}/generate`,
      { method: 'POST' }
    )
    set((s) => {
      if (!s.currentProject) return s
      const chapters = s.currentProject.chapters.map((ch) =>
        ch.id === chapterId ? chapter : ch
      )
      return { currentProject: { ...s.currentProject, chapters } }
    })
  },

  generateAll: async (projectId, voiceId, model) => {
    set({ generating: true, generationProgress: null })
    try {
      const res = await fetch(`${BACKEND_URL}/api/projects/${projectId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voice_id: voiceId || undefined,
          model: model || undefined,
          language: get().currentProject?.language || 'en',
          speed: 1.0,
        }),
      })

      if (!res.ok) throw new Error('Generation failed')

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.chapter) {
                set({ generationProgress: data })
                // Update chapter status in store
                if (data.status === 'completed' || data.status === 'error') {
                  await get().fetchProject(projectId)
                }
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      }

      // Final refresh
      await get().fetchProject(projectId)
    } finally {
      set({ generating: false, generationProgress: null })
    }
  },

  mergeExport: async (projectId, format, acxCompliant) => {
    const result = await apiFetch<{ status: string; path: string; format: string }>(
      `/projects/${projectId}/merge`,
      {
        method: 'POST',
        body: JSON.stringify({ format, gap_seconds: 2.0, acx_compliant: acxCompliant || false }),
      }
    )
    return result.path
  },

  exportChaptersACX: async (projectId) => {
    return await apiFetch(`/projects/${projectId}/export-chapters`, { method: 'POST' })
  },

  deleteProject: async (id) => {
    await apiFetch(`/projects/${id}`, { method: 'DELETE' })
    set((s) => ({
      projects: s.projects.filter((p) => p.id !== id),
      currentProject: s.currentProject?.id === id ? null : s.currentProject,
    }))
  },

  fetchKokoroVoices: async () => {
    try {
      const data = await apiFetch<{ voices: KokoroVoice[] }>('/projects/kokoro-voices')
      set({ kokoroVoices: data.voices })
    } catch {
      // ignore
    }
  },
}))
