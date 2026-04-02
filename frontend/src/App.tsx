import { Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import Studio from './pages/Studio'
import Voices from './pages/Voices'
import CloneVoice from './pages/CloneVoice'
import Projects from './pages/Projects'
import ProjectEditor from './pages/ProjectEditor'
import History from './pages/History'
import Models from './pages/Models'
import Settings from './pages/Settings'
import SpeechToText from './pages/SpeechToText'
import SpeechToSpeech from './pages/SpeechToSpeech'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Studio />} />
        <Route path="/voices" element={<Voices />} />
        <Route path="/clone" element={<CloneVoice />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:id" element={<ProjectEditor />} />
        <Route path="/speech-to-text" element={<SpeechToText />} />
        <Route path="/speech-to-speech" element={<SpeechToSpeech />} />
        <Route path="/history" element={<History />} />
        <Route path="/models" element={<Models />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
