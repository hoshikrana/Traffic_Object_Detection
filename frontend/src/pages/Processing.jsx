import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { CheckCircle2, Wifi, WifiOff, Clock, ArrowRight } from 'lucide-react'
import useJobWebSocket from '../hooks/useJobWebSocket'
import MetricsGrid from '../components/MetricsGrid'
import ProgressBar from '../components/ProgressBar'
import DensityChart from '../components/DensityChart'

export default function Processing() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { wsStatus, latestAnalytics, progress, isComplete, summary } = useJobWebSocket(jobId)
  const [job, setJob] = useState(null)
  const [analyticsHistory, setAnalyticsHistory] = useState([])
  const [statusLog, setStatusLog] = useState([])
  const logEndRef = useRef(null)
  const prevCongestion = useRef(null)

  // Fetch initial job info
  useEffect(() => {
    const fetchJob = async () => {
      try {
        const resp = await fetch(`/api/jobs/${jobId}`)
        if (resp.ok) setJob(await resp.json())
      } catch (err) {
        console.warn('Failed to fetch job:', err)
      }
    }
    fetchJob()
  }, [jobId])

  // Accumulate analytics for chart
  useEffect(() => {
    if (latestAnalytics) {
      setAnalyticsHistory(prev => {
        const next = [...prev, latestAnalytics].slice(-60) // Keep last 60 points
        return next
      })

      // Log congestion changes
      const congestion = latestAnalytics.congestion_level
      if (congestion && congestion !== prevCongestion.current) {
        addLog(`Congestion: ${congestion}`, congestion === 'CRITICAL' ? 'error' : 'info')
        prevCongestion.current = congestion
      }
    }
  }, [latestAnalytics])

  // Log WebSocket status changes
  useEffect(() => {
    if (wsStatus === 'connected') addLog('Connected to server', 'success')
    else if (wsStatus === 'disconnected') addLog('Connection lost', 'warning')
  }, [wsStatus])

  // Auto-navigate on completion
  useEffect(() => {
    if (isComplete) {
      addLog('Analysis complete!', 'success')
      const timer = setTimeout(() => navigate(`/results/${jobId}`), 3000)
      return () => clearTimeout(timer)
    }
  }, [isComplete, jobId, navigate])

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [statusLog])

  function addLog(message, type = 'info') {
    const time = new Date().toLocaleTimeString()
    setStatusLog(prev => [...prev, { time, message, type }])
  }

  const logColors = {
    info: 'text-gray-400',
    success: 'text-emerald-400',
    warning: 'text-amber-400',
    error: 'text-red-400',
  }

  return (
    <div className="min-h-[calc(100vh-64px)] p-4 md:p-6 max-w-7xl mx-auto">
      {/* Connection status banner */}
      {wsStatus === 'disconnected' && (
        <div className="mb-4 flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2.5 text-amber-400 text-sm">
          <WifiOff size={16} />
          Connection lost — attempting to reconnect...
        </div>
      )}

      {/* Completion banner */}
      {isComplete && (
        <div className="mb-4 flex items-center justify-between bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-4 py-3">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 size={18} />
            <span className="font-medium">Analysis complete!</span>
            <span className="text-emerald-500/60 text-sm">Redirecting in 3s...</span>
          </div>
          <button
            onClick={() => navigate(`/results/${jobId}`)}
            className="flex items-center gap-1 px-4 py-1.5 bg-emerald-500 text-white rounded-lg text-sm font-medium hover:bg-emerald-400 transition-colors"
          >
            View Results <ArrowRight size={14} />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 md:gap-6">
        {/* LEFT COLUMN */}
        <div className="lg:col-span-2 space-y-4">
          {/* Job info */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300">Job Details</h2>
              <div className="flex items-center gap-1.5">
                {wsStatus === 'connected' ? (
                  <Wifi size={12} className="text-emerald-400" />
                ) : (
                  <WifiOff size={12} className="text-amber-400" />
                )}
                <span className={`text-[10px] uppercase tracking-wider ${
                  wsStatus === 'connected' ? 'text-emerald-400' : 'text-amber-400'
                }`}>
                  {wsStatus}
                </span>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">File</span>
                <span className="text-gray-300 truncate max-w-[200px]">{job?.original_filename || '...'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Status</span>
                <span className="px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-400">
                  {job?.status || 'processing'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Started</span>
                <span className="text-gray-400 text-xs flex items-center gap-1">
                  <Clock size={10} />
                  {job?.started_at ? new Date(job.started_at).toLocaleTimeString() : '...'}
                </span>
              </div>
            </div>
          </div>

          {/* Progress */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <ProgressBar
              progress={progress}
              label="Processing"
            />
            <p className="text-xs text-gray-600 mt-2">
              Frame {latestAnalytics?.frame_number || 0} {job?.total_frames ? `of ~${job.total_frames}` : ''}
            </p>
          </div>

          {/* Live metrics */}
          <MetricsGrid analytics={latestAnalytics} />
        </div>

        {/* RIGHT COLUMN */}
        <div className="lg:col-span-3 space-y-4">
          {/* Density chart */}
          <DensityChart data={analyticsHistory} />

          {/* Status log */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Activity Log</h3>
            <div className="h-48 overflow-y-auto space-y-1 font-mono text-xs">
              {statusLog.length === 0 ? (
                <p className="text-gray-700 text-center py-8">Waiting for events...</p>
              ) : (
                statusLog.map((entry, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-gray-600 whitespace-nowrap">[{entry.time}]</span>
                    <span className={logColors[entry.type] || 'text-gray-400'}>{entry.message}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
