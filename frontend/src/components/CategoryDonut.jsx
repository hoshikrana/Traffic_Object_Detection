import { useMemo } from 'react'
import Chart from 'react-apexcharts'

export default function CategoryDonut({ categories = {} }) {
  const { labels, series, colors } = useMemo(() => {
    const mapping = [
      { key: 'cars', label: 'Cars', color: '#FFB432' },
      { key: 'vans', label: 'Vans', color: '#64C8FF' },
      { key: 'trucks', label: 'Trucks', color: '#3232FF' },
      { key: 'buses', label: 'Buses', color: '#00A5FF' },
      { key: 'others', label: 'Others', color: '#C864FF' },
    ]
    return {
      labels: mapping.map(m => m.label),
      series: mapping.map(m => categories[m.key] || 0),
      colors: mapping.map(m => m.color),
    }
  }, [categories])

  const total = series.reduce((a, b) => a + b, 0)

  const options = useMemo(() => ({
    chart: {
      type: 'donut',
      background: 'transparent',
    },
    theme: { mode: 'dark' },
    colors,
    labels,
    stroke: { width: 2, colors: ['#111827'] },
    dataLabels: { enabled: false },
    legend: {
      position: 'bottom',
      labels: { colors: '#9ca3af' },
      fontSize: '12px',
      markers: { size: 8, offsetX: -3 },
    },
    plotOptions: {
      pie: {
        donut: {
          size: '68%',
          labels: {
            show: true,
            name: {
              show: true,
              fontSize: '12px',
              color: '#9ca3af',
              offsetY: -5,
            },
            value: {
              show: true,
              fontSize: '22px',
              fontWeight: 700,
              color: '#ffffff',
              formatter: () => total.toString(),
            },
            total: {
              show: true,
              label: 'Total',
              fontSize: '12px',
              color: '#6b7280',
              formatter: () => total.toString(),
            },
          },
        },
      },
    },
    tooltip: {
      theme: 'dark',
      y: { formatter: (val) => `${val} vehicles` },
    },
  }), [colors, labels, total])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">Vehicle Types</h3>
      {total === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
          No data yet
        </div>
      ) : (
        <Chart options={options} series={series} type="donut" height={240} />
      )}
    </div>
  )
}
