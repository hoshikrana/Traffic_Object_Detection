import { CheckCircle2, AlertTriangle } from 'lucide-react'

export default function IncidentTable({ incidents = [] }) {
  if (incidents.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-full">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          Detected Incidents
          <span className="ml-2 px-2 py-0.5 text-xs bg-gray-800 text-gray-400 rounded-full">0</span>
        </h3>
        <div className="flex flex-col items-center justify-center py-12 text-gray-600">
          <CheckCircle2 size={40} className="text-emerald-500/50 mb-3" />
          <p className="text-sm">No incidents detected</p>
          <p className="text-xs text-gray-700 mt-1">All vehicles moving normally</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-full">
      <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
        <AlertTriangle size={14} className="text-red-400" />
        Detected Incidents
        <span className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full font-mono">
          {incidents.length}
        </span>
      </h3>
      <div className="overflow-y-auto max-h-80">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
              <th className="text-left pb-2 pr-2">Track</th>
              <th className="text-left pb-2 pr-2">Type</th>
              <th className="text-left pb-2 pr-2">Frame</th>
              <th className="text-left pb-2 pr-2">Location</th>
              <th className="text-left pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc, idx) => (
              <tr
                key={inc.id || idx}
                className="border-b border-gray-800/50 hover:bg-red-500/5 transition-colors duration-150"
              >
                <td className="py-2 pr-2 font-mono text-cyan-400">#{inc.track_id}</td>
                <td className="py-2 pr-2 text-gray-300 capitalize">
                  {(inc.incident_type || 'stopped').replace('_', ' ')}
                </td>
                <td className="py-2 pr-2 font-mono text-gray-400">{inc.frame_number}</td>
                <td className="py-2 pr-2 font-mono text-gray-500 text-xs">
                  ({Math.round(inc.x)}, {Math.round(inc.y)})
                </td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    inc.resolved
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {inc.resolved ? 'Resolved' : 'Active'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
