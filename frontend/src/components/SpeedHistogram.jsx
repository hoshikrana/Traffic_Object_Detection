import { useMemo } from 'react'
import Chart from 'react-apexcharts'

export default function SpeedHistogram({ data = [] }) {
  const bins = useMemo(() => {
    const ranges = [
      { label: '0-20', min: 0, max: 20, count: 0, color: '#22c55e' },
      { label: '20-40', min: 20, max: 40, count: 0, color: '#84cc16' },
      { label: '40-60', min: 40, max: 60, count: 0, color: '#eab308' },
      { label: '60-80', min: 60, max: 80, count: 0, color: '#f97316' },
      { label: '80+', min: 80, max: Infinity, count: 0, color: '#ef4444' },
    ]

    data.forEach(d => {
      const speed = d.avg_speed_kmh || 0
      for (const bin of ranges) {
        if (speed >= bin.min && speed < bin.max) {
          bin.count++
          break
        }
      }
    })

    return ranges
  }, [data])

  const options = useMemo(() => ({
    chart: {
      type: 'bar',
      background: 'transparent',
      toolbar: { show: false },
    },
    theme: { mode: 'dark' },
    colors: bins.map(b => b.color),
    plotOptions: {
      bar: {
        borderRadius: 4,
        distributed: true,
        columnWidth: '65%',
      },
    },
    dataLabels: {
      enabled: true,
      style: { colors: ['#fff'], fontSize: '11px' },
    },
    legend: { show: false },
    grid: {
      borderColor: '#1f2937',
      strokeDashArray: 3,
      xaxis: { lines: { show: false } },
    },
    xaxis: {
      categories: bins.map(b => b.label),
      labels: { style: { colors: '#9ca3af', fontSize: '11px' } },
      title: { text: 'km/h', style: { color: '#6b7280', fontSize: '11px' } },
    },
    yaxis: {
      labels: { style: { colors: '#9ca3af', fontSize: '11px' } },
      title: { text: 'Count', style: { color: '#6b7280', fontSize: '11px' } },
    },
    tooltip: {
      theme: 'dark',
      y: { formatter: (val) => `${val} snapshots` },
    },
  }), [bins])

  const series = [{ name: 'Snapshots', data: bins.map(b => b.count) }]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">Speed Distribution</h3>
      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
          No data yet
        </div>
      ) : (
        <Chart options={options} series={series} type="bar" height={220} />
      )}
    </div>
  )
}
