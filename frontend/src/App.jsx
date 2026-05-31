import { Routes, Route, Link } from 'react-router-dom'
import { Eye, ExternalLink } from 'lucide-react'
import Upload from './pages/Upload'
import Processing from './pages/Processing'
import Results from './pages/Results'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950">
      {/* Persistent Header */}
      <header className="sticky top-0 z-50 border-b border-gray-800/50 bg-gray-950/80 backdrop-blur-lg">
        <div className="max-w-[1400px] mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="p-1.5 rounded-lg bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/30 group-hover:border-emerald-400/50 transition-colors">
              <Eye size={18} className="text-emerald-400" />
            </div>
            <span className="text-lg font-semibold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              TrafficVision
            </span>
          </Link>

          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            <ExternalLink size={16} />
            <span className="hidden sm:inline">View Source</span>
          </a>
        </div>
      </header>

      {/* Routes */}
      <main>
        <Routes>
          <Route path="/" element={<Upload />} />
          <Route path="/processing/:jobId" element={<Processing />} />
          <Route path="/results/:jobId" element={<Results />} />
        </Routes>
      </main>
    </div>
  )
}
