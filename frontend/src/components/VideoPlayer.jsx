import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Pause, Maximize, Download } from 'lucide-react'

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function VideoPlayer({ src, jobId }) {
  const videoRef = useRef(null)
  const containerRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [showControls, setShowControls] = useState(true)
  const hideTimerRef = useRef(null)

  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      video.play()
      setPlaying(true)
    } else {
      video.pause()
      setPlaying(false)
    }
  }, [])

  const handleSeek = useCallback((e) => {
    const video = videoRef.current
    if (!video) return
    video.currentTime = parseFloat(e.target.value)
  }, [])

  const changeSpeed = useCallback((newSpeed) => {
    const video = videoRef.current
    if (!video) return
    video.playbackRate = newSpeed
    setSpeed(newSpeed)
  }, [])

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current
    if (!container) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      container.requestFullscreen()
    }
  }, [])

  const handleMouseMove = useCallback(() => {
    setShowControls(true)
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
    hideTimerRef.current = setTimeout(() => {
      if (playing) setShowControls(false)
    }, 3000)
  }, [playing])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const onTimeUpdate = () => setCurrentTime(video.currentTime)
    const onDurationChange = () => setDuration(video.duration)
    const onEnded = () => setPlaying(false)

    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('durationchange', onDurationChange)
    video.addEventListener('ended', onEnded)

    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('durationchange', onDurationChange)
      video.removeEventListener('ended', onEnded)
    }
  }, [])

  const seekPercent = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <h3 className="text-sm font-semibold text-gray-300 px-4 pt-4 mb-2">
        Annotated Output Video
      </h3>
      <div
        ref={containerRef}
        className="relative bg-black cursor-pointer group"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => playing && setShowControls(false)}
      >
        <video
          ref={videoRef}
          src={src}
          className="w-full aspect-video"
          onClick={togglePlay}
          preload="metadata"
        />

        {/* Controls overlay */}
        <div className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3 transition-opacity duration-300 ${showControls ? 'opacity-100' : 'opacity-0'}`}>
          {/* Seek bar */}
          <div className="mb-2">
            <input
              type="range"
              min="0"
              max={duration || 0}
              step="0.1"
              value={currentTime}
              onChange={handleSeek}
              className="w-full"
              style={{
                background: `linear-gradient(to right, #10b981 0%, #10b981 ${seekPercent}%, #374151 ${seekPercent}%, #374151 100%)`
              }}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Play/Pause */}
              <button onClick={togglePlay} className="text-white hover:text-emerald-400 transition-colors">
                {playing ? <Pause size={20} /> : <Play size={20} />}
              </button>

              {/* Time display */}
              <span className="text-xs font-mono text-gray-400">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {/* Speed selector */}
              <div className="flex gap-1">
                {[0.5, 1, 1.5, 2].map(s => (
                  <button
                    key={s}
                    onClick={() => changeSpeed(s)}
                    className={`px-1.5 py-0.5 text-xs rounded font-mono transition-colors ${
                      speed === s
                        ? 'bg-emerald-500/30 text-emerald-400'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              {/* Fullscreen */}
              <button onClick={toggleFullscreen} className="text-gray-400 hover:text-white transition-colors">
                <Maximize size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Download link */}
      {src && (
        <div className="px-4 py-3 border-t border-gray-800">
          <a
            href={src}
            download={`annotated_${jobId}.mp4`}
            className="inline-flex items-center gap-2 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <Download size={14} />
            Download annotated video
          </a>
        </div>
      )}
    </div>
  )
}
