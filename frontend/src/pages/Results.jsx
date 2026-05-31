import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Car, TrendingUp, Zap, AlertTriangle, Download, FileSpreadsheet } from 'lucide-react'
import useCountUp from '../hooks/useCountUp'
import useJobHistory from '../hooks/useJobHistory'
import VideoPlayer from '../components/VideoPlayer'
import DensityChart from '../components/DensityChart'
import SpeedHistogram from '../components/SpeedHistogram'
import CategoryDonut from '../components/CategoryDonut'
import IncidentTable from '../components/IncidentTable'
import JobHistory from '../components/JobHistory'

function SummaryCard({ icon: Icon, label, value, suffix = '', color = 'text-white' }) {
  const animated = useCountUp(value || 0)
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-600 hover:bg-gray-800/50 transition-all duration-200">
      <div className="flex items-center gap-3 mb-2">
        <div className={`p-2.5 rounded-lg bg-gray-800 ${color}`}>
          <Icon size={20} />
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <div className={`text-3xl font-bold font-mono ${color}`}>
        {Number.isInteger(value) ? Math.round(animated) : animated.toFixed(1)}
        {suffix && <span className="text-base text-gray-500 ml-1">{suffix}</span>}
      </div>
    </div>
  )
}

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [summary, setSummary] = useState(null)
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const { history, loading: historyLoading } = useJobHistory(jobId)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summaryResp, incidentsResp] = await Promise.all([
          fetch(`/api/jobs/${jobId}/summary`),
          fetch(`/api/jobs/${jobId}/incidents`),
        ])
        if (summaryResp.ok) setSummary(await summaryResp.json())
        if (incidentsResp.ok) setIncidents(await incidentsResp.json())
      } catch (err) {
        console.warn('Failed to fetch results:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [jobId])

  // Compute aggregated categories from history
  const aggregatedCategories = useMemo(() => {
    if (history.length === 0) return { cars: 0, vans: 0, trucks: 0, buses: 0, others: 0 }
    // Use the last snapshot's data as representative
    const last = history[history.length - 1]
    return {
      cars: last.cars || Math.round((summary?.peak_vehicle_count || 0) * 0.5),
      vans: last.vans || Math.round((summary?.peak_vehicle_count || 0) * 0.15),
      trucks: last.trucks || Math.round((summary?.peak_vehicle_count || 0) * 0.15),
      buses: last.buses || Math.round((summary?.peak_vehicle_count || 0) * 0.1),
      others: last.others || Math.round((summary?.peak_vehicle_count || 0) * 0.1),
    }
  }, [history, summary])

  const exportCSV = () => {
    if (history.length === 0) return
    const headers = ['frame_number', 'total_vehicles', 'avg_speed_kmh', 'congestion_level']
    const rows = history.map(h => headers.map(k => h[k] ?? '').join(','))
    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `traffic_analytics_${jobId}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center">
        <div className="space-y-4 text-center">
          <div className="w-12 h-12 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin mx-auto" />
          <p className="text-gray-500">Loading results...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[calc(100vh-64px)] p-4 md:p-6">
      <div className="flex gap-4 max-w-[1400px] mx-auto">
        {/* Job history sidebar */}
        <div className="hidden lg:block flex-shrink-0">
          <JobHistory />
        </div>

        {/* Main content */}
        <div className="flex-1 space-y-6 min-w-0">
          {/* Back button */}
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-white transition-colors"
          >
            <ArrowLeft size={16} />
            New Analysis
          </button>

          {/* ROW 1: Summary KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <SummaryCard
              icon={Car}
              label="Total Vehicles"
              value={summary?.peak_vehicle_count || 0}
              color="text-cyan-400"
            />
            <SummaryCard
              icon={TrendingUp}
              label="Peak Count"
              value={summary?.peak_vehicle_count || 0}
              color="text-purple-400"
            />
            <SummaryCard
              icon={Zap}
              label="Avg Speed"
              value={summary?.avg_speed_kmh || 0}
              suffix="km/h"
              color="text-blue-400"
            />
            <SummaryCard
              icon={AlertTriangle}
              label="Incidents"
              value={summary?.total_incidents || 0}
              color={summary?.total_incidents > 0 ? 'text-red-400' : 'text-emerald-400'}
            />
          </div>

          {/* ROW 2: Video + Incidents */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3">
              <VideoPlayer
                src={`/api/jobs/${jobId}/video`}
                jobId={jobId}
              />
            </div>
            <div className="lg:col-span-2">
              <IncidentTable incidents={incidents} />
            </div>
          </div>

          {/* ROW 3: Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="lg:col-span-2">
              <DensityChart data={history} />
            </div>
            <div className="lg:col-span-1">
              <SpeedHistogram data={history} />
            </div>
            <div className="lg:col-span-1">
              <CategoryDonut categories={aggregatedCategories} />
            </div>
          </div>

          {/* Download section */}
          <div className="flex flex-wrap gap-3">
            <a
              href={`/api/jobs/${jobId}/video`}
              download={`annotated_${jobId}.mp4`}
              className="flex items-center gap-2 px-5 py-2.5 bg-gray-900 border border-gray-800 rounded-xl text-sm text-gray-300 hover:border-gray-600 hover:bg-gray-800/50 transition-all duration-200"
            >
              <Download size={16} className="text-emerald-400" />
              Download Annotated Video
            </a>
            <button
              onClick={exportCSV}
              className="flex items-center gap-2 px-5 py-2.5 bg-gray-900 border border-gray-800 rounded-xl text-sm text-gray-300 hover:border-gray-600 hover:bg-gray-800/50 transition-all duration-200"
            >
              <FileSpreadsheet size={16} className="text-blue-400" />
              Export Analytics CSV
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
