import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Upload, Trash2, FileText, Plus, Clock, CheckCircle2, Link } from 'lucide-react'
import { useProjectStore } from '../stores/projectStore'
import { apiFetch } from '../lib/api'

export default function Projects() {
  const { projects, loading, fetchProjects, uploadBook, createFromText, deleteProject } =
    useProjectStore()
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [showTextInput, setShowTextInput] = useState(false)
  const [textName, setTextName] = useState('')
  const [textContent, setTextContent] = useState('')
  const [uploading, setUploading] = useState(false)
  const [showLinkInput, setShowLinkInput] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const project = await uploadBook(file, '')
      navigate(`/projects/${project.id}`)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleLinkImport = async () => {
    if (!linkUrl.trim()) return
    setUploading(true)
    try {
      const project = await apiFetch<any>('/projects/import-url', {
        method: 'POST',
        body: JSON.stringify({ url: linkUrl.trim() }),
      })
      navigate(`/projects/${project.id}`)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Import failed')
    } finally {
      setUploading(false)
      setLinkUrl('')
      setShowLinkInput(false)
    }
  }

  const handleCreateText = async () => {
    if (!textName.trim() || !textContent.trim()) return
    setUploading(true)
    try {
      const project = await createFromText(textName, textContent)
      navigate(`/projects/${project.id}`)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Creation failed')
    } finally {
      setUploading(false)
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400'
      case 'generating': return 'text-yellow-400'
      case 'error': return 'text-red-400'
      default: return 'text-zinc-500'
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Audiobooks</h1>
      </div>

      {/* Upload area */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div
          className="border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center cursor-pointer hover:border-violet-500/50 transition-colors"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const f = e.dataTransfer.files[0]
            if (f) handleUpload(f)
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.epub,.pdf,.docx"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleUpload(f)
            }}
          />
          <Upload className="w-10 h-10 text-violet-500/60 mx-auto mb-3" />
          <p className="text-sm text-zinc-300 mb-1">Upload a Book</p>
          <p className="text-xs text-zinc-500">TXT, EPUB, PDF, DOCX</p>
          {uploading && <p className="text-xs text-violet-400 mt-2">Processing...</p>}
        </div>

        <div
          className="border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center cursor-pointer hover:border-violet-500/50 transition-colors"
          onClick={() => setShowTextInput(true)}
        >
          <Plus className="w-10 h-10 text-violet-500/60 mx-auto mb-3" />
          <p className="text-sm text-zinc-300 mb-1">Paste Text</p>
          <p className="text-xs text-zinc-500">Create from text directly</p>
        </div>

        <div
          className="border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center cursor-pointer hover:border-violet-500/50 transition-colors"
          onClick={() => setShowLinkInput(true)}
        >
          <Link className="w-10 h-10 text-violet-500/60 mx-auto mb-3" />
          <p className="text-sm text-zinc-300 mb-1">Import from URL</p>
          <p className="text-xs text-zinc-500">Google Docs, Web Pages</p>
        </div>
      </div>

      {/* Text input modal */}
      {showTextInput && (
        <div className="mb-8 bg-zinc-900 border border-zinc-700 rounded-xl p-6 space-y-4">
          <input
            value={textName}
            onChange={(e) => setTextName(e.target.value)}
            placeholder="Project name"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500"
          />
          <textarea
            value={textContent}
            onChange={(e) => setTextContent(e.target.value)}
            placeholder="Paste your book text here... Chapters will be auto-detected."
            rows={8}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm resize-y focus:outline-none focus:border-violet-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreateText}
              disabled={!textName.trim() || !textContent.trim() || uploading}
              className="px-4 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded-lg text-sm"
            >
              {uploading ? 'Creating...' : 'Create Audiobook'}
            </button>
            <button
              onClick={() => setShowTextInput(false)}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Link input */}
      {showLinkInput && (
        <div className="mb-8 bg-zinc-900 border border-zinc-700 rounded-xl p-6 space-y-4">
          <p className="text-sm text-zinc-300">Import from Google Docs or Web URL</p>
          <p className="text-[10px] text-zinc-500">For Google Docs, make sure sharing is set to "Anyone with the link can view"</p>
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://docs.google.com/document/d/... or any URL"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleLinkImport}
              disabled={!linkUrl.trim() || uploading}
              className="px-4 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-zinc-700 rounded-lg text-sm"
            >
              {uploading ? 'Importing...' : 'Import'}
            </button>
            <button
              onClick={() => { setShowLinkInput(false); setLinkUrl('') }}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Projects list */}
      {projects.length === 0 && !loading ? (
        <div className="text-center text-zinc-500 py-16">
          <BookOpen className="w-12 h-12 mx-auto mb-3 text-zinc-700" />
          <p>No audiobooks yet</p>
          <p className="text-sm mt-1">Upload a book or paste text to get started</p>
        </div>
      ) : (
        <div className="space-y-2">
          {projects.map((proj) => (
            <div
              key={proj.id}
              onClick={() => navigate(`/projects/${proj.id}`)}
              className="flex items-center gap-4 p-4 bg-zinc-900 border border-zinc-700 rounded-lg hover:border-zinc-600 cursor-pointer transition-colors"
            >
              <FileText className="w-5 h-5 text-violet-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium truncate">{proj.name}</h3>
                <p className="text-xs text-zinc-500">
                  {proj.chapters.length} chapters
                  {proj.total_duration ? ` / ${Math.round(proj.total_duration / 60)}m` : ''}
                  {proj.source_filename ? ` / ${proj.source_filename}` : ''}
                </p>
              </div>
              <span className={`text-xs ${statusColor(proj.status)}`}>
                {proj.status === 'completed' && <CheckCircle2 className="w-4 h-4 inline mr-1" />}
                {proj.status === 'generating' && <Clock className="w-4 h-4 inline mr-1 animate-spin" />}
                {proj.status}
              </span>
              <span className="text-xs text-zinc-600">
                {new Date(proj.created_at).toLocaleDateString()}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm('Delete this audiobook?')) deleteProject(proj.id)
                }}
                className="text-zinc-600 hover:text-red-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
