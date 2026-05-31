import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { History, ChevronRight, Clock, CheckCircle2, Loader2, AlertCircle, ChevronLeft } from 'lucide-react'

const statusConfig = {
  queued: { color: 'bg-gray-500/20 text-gray-400', icon: Clock },
  processing: { color: 'bg-blue-500/20 text-blue-400', icon: Loader2 },
  completed: { color: 'bg-emerald-500/20 text-emerald-400', icon: CheckCircle2 },
  failed: { color: 'bg-red-500/20 text-red-400', icon: AlertCircle },
}

export default function JobHistory({ collapsed = false, onToggle }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [isOpen, setIsOpen] = useState(!collapsed)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const resp = await fetch('/api/jobs')
        if (resp.ok) {
          setJobs(await resp.json())
        }
      } catch (err) {
        console.warn('Failed to fetch jobs:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchJobs()
  }, [])

  const toggle = () => {
    setIsOpen(!isOpen)
    onToggle?.(!isOpen)
  }

  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl transition-all duration-300 ${isOpen ? 'w-72' : 'w-12'}`}>
      {/* Toggle button */}
      <button
        onClick={toggle}
        className="w-full flex items-center gap-2 p-3 text-gray-400 hover:text-white transition-colors"
      >
        {isOpen ? <ChevronLeft size={16} /> : <History size={16} />}
        {isOpen && <span className="text-sm font-medium">Job History</span>}
      </button>

      {/* Job list */}
      {isOpen && (
        <div className="px-2 pb-3 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={20} className="text-gray-600 animate-spin" />
            </div>
          ) : jobs.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-4">No jobs yet</p>
          ) : (
            <div className="space-y-1">
              {jobs.map(job => {
                const config = statusConfig[job.status] || statusConfig.queued
                const StatusIcon = config.icon
                const createdAt = new Date(job.created_at).toLocaleString()

                return (
                  <button
                    key={job.id}
                    onClick={() => {
                      if (job.status === 'completed') navigate(`/results/${job.id}`)
                      else if (job.status === 'processing') navigate(`/processing/${job.id}`)
                    }}
                    className="w-full text-left p-2.5 rounded-lg hover:bg-gray-800/60 transition-colors group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-300 truncate max-w-[140px] font-medium">
                        {job.original_filename}
                      </span>
                      <ChevronRight size={12} className="text-gray-700 group-hover:text-gray-400 transition-colors" />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded-full ${config.color}`}>
                        <StatusIcon size={10} className={job.status === 'processing' ? 'animate-spin' : ''} />
                        {job.status}
                      </span>
                      <span className="text-[10px] text-gray-600">{createdAt}</span>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
