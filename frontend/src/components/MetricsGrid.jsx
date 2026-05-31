import { Car, Gauge, Zap, AlertTriangle } from 'lucide-react'
import useCountUp from '../hooks/useCountUp'

const congestionColors = {
  LOW: 'text-emerald-400',
  MODERATE: 'text-amber-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-red-400',
}

const congestionBorderColors = {
  LOW: 'border-emerald-500/30',
  MODERATE: 'border-amber-500/30',
  HIGH: 'border-orange-500/30',
  CRITICAL: 'border-red-500/30',
}

function MetricCard({ icon: Icon, label, value, suffix = '', color = 'text-white', borderColor = 'border-gray-800', isText = false, pulse = false }) {
  const animatedValue = useCountUp(isText ? 0 : (value || 0))

  return (
    <div className={`bg-gray-900 border ${borderColor} rounded-xl p-4 md:p-5 hover:border-gray-600 hover:bg-gray-800/50 transition-all duration-200 ${pulse ? 'animate-pulse-glow' : ''}`}>
      <div className="flex items-center gap-3 mb-2">
        <div className={`p-2 rounded-lg bg-gray-800 ${color}`}>
          <Icon size={18} />
        </div>
        <span className="text-sm text-gray-400 font-medium">{label}</span>
      </div>
      <div className={`text-2xl font-bold font-mono ${color}`}>
        {isText ? value : Math.round(animatedValue)}
        {suffix && <span className="text-sm text-gray-500 ml-1">{suffix}</span>}
      </div>
    </div>
  )
}

export default function MetricsGrid({ analytics }) {
  const data = analytics || {}
  const vehicles = data.total_vehicles || 0
  const congestion = data.congestion_level || 'LOW'
  const avgSpeed = data.avg_speed_kmh || 0
  const incidents = data.active_incidents?.length || 0

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <MetricCard
        icon={Car}
        label="Vehicles"
        value={vehicles}
        color="text-cyan-400"
        borderColor="border-cyan-500/20"
      />
      <MetricCard
        icon={Gauge}
        label="Congestion"
        value={congestion}
        isText={true}
        color={congestionColors[congestion] || 'text-emerald-400'}
        borderColor={congestionBorderColors[congestion] || 'border-emerald-500/30'}
        pulse={congestion === 'CRITICAL'}
      />
      <MetricCard
        icon={Zap}
        label="Avg Speed"
        value={avgSpeed}
        suffix="km/h"
        color="text-blue-400"
        borderColor="border-blue-500/20"
      />
      <MetricCard
        icon={AlertTriangle}
        label="Incidents"
        value={incidents}
        color={incidents > 0 ? 'text-red-400' : 'text-emerald-400'}
        borderColor={incidents > 0 ? 'border-red-500/30' : 'border-emerald-500/20'}
        pulse={incidents > 0}
      />
    </div>
  )
}
