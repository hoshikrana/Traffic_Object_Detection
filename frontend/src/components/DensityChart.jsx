import { useMemo } from 'react'
import Chart from 'react-apexcharts'

export default function DensityChart({ data = [] }) {
  const { series, categories } = useMemo(() => {
    const vehicleCounts = data.map(d => d.total_vehicles || 0)
    const frameNumbers = data.map(d => d.frame_number || 0)
    return {
      series: [{ name: 'Vehicles', data: vehicleCounts }],
      categories: frameNumbers,
    }
  }, [data])

  const options = useMemo(() => ({
    chart: {
      type: 'area',
      background: 'transparent',
      toolbar: { show: false },
      zoom: { enabled: false },
      animations: {
        enabled: true,
        easing: 'easeinout',
        dynamicAnimation: { speed: 300 },
      },
    },
    theme: { mode: 'dark' },
    colors: ['#10b981'],
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.45,
        opacityTo: 0.05,
        stops: [0, 100],
        colorStops: [
          { offset: 0, color: '#10b981', opacity: 0.4 },
          { offset: 100, color: '#10b981', opacity: 0.02 },
        ],
      },
    },
    stroke: { curve: 'smooth', width: 2 },
    dataLabels: { enabled: false },
    markers: { size: 0 },
    grid: {
      borderColor: '#1f2937',
      strokeDashArray: 3,
      xaxis: { lines: { show: false } },
    },
    xaxis: {
      categories,
      labels: {
        style: { colors: '#6b7280', fontSize: '10px' },
        rotate: 0,
        hideOverlappingLabels: true,
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
      title: { text: 'Frame', style: { color: '#6b7280', fontSize: '11px' } },
    },
    yaxis: {
      labels: { style: { colors: '#6b7280', fontSize: '11px' } },
      title: { text: 'Count', style: { color: '#6b7280', fontSize: '11px' } },
    },
    annotations: {
      yaxis: [
        {
          y: 18,
          borderColor: '#f97316',
          strokeDashArray: 4,
          label: {
            text: 'HIGH threshold',
            position: 'left',
            style: {
              color: '#fff',
              background: '#f97316',
              fontSize: '10px',
              padding: { left: 6, right: 6, top: 2, bottom: 2 },
            },
          },
        },
      ],
    },
    tooltip: {
      theme: 'dark',
      x: { formatter: (val) => `Frame ${val}` },
      y: { formatter: (val) => `${val} vehicles` },
    },
  }), [categories])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">Vehicle Density</h3>
      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
          Waiting for data...
        </div>
      ) : (
        <Chart options={options} series={series} type="area" height={220} />
      )}
    </div>
  )
}
