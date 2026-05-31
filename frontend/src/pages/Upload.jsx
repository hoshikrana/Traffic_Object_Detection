import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload as UploadIcon, Film, Zap, Shield, Target, Loader2, X, AlertCircle } from 'lucide-react'
import ProgressBar from '../components/ProgressBar'
import JobHistory from '../components/JobHistory'

const features = [
  { icon: Target, label: 'ByteTrack Tracking', desc: 'Multi-object tracking' },
  { icon: Zap, label: 'Speed Estimation', desc: 'Real-time speed calc' },
  { icon: Shield, label: 'Incident Detection', desc: 'Stopped vehicle alerts' },
]

export default function Upload() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const videoRef = useRef(null)

  const onDrop = useCallback((accepted, rejected) => {
    setError(null)
    if (rejected.length > 0) {
      const err = rejected[0].errors[0]
      setError(err.message || 'Invalid file')
      return
    }
    if (accepted.length > 0) {
      const f = accepted[0]
      setFile(f)
      setPreview(URL.createObjectURL(f))
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: { 'video/mp4': ['.mp4'], 'video/quicktime': ['.mov'], 'video/x-msvideo': ['.avi'] },
    maxSize: 500 * 1024 * 1024,
    maxFiles: 1,
    multiple: false,
  })

  const clearFile = () => {
    setFile(null)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(null)
    setError(null)
    setUploadProgress(0)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('file', file)

    try {
      // Use XMLHttpRequest for progress tracking
      const result = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/jobs/upload')

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setUploadProgress((e.loaded / e.total) * 100)
          }
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText))
          } else {
            try {
              const errData = JSON.parse(xhr.responseText)
              reject(new Error(errData.detail || `Upload failed (${xhr.status})`))
            } catch {
              reject(new Error(`Upload failed (${xhr.status})`))
            }
          }
        }

        xhr.onerror = () => reject(new Error('Network error'))
        xhr.send(formData)
      })

      navigate(`/processing/${result.job_id}`)
    } catch (err) {
      setError(err.message)
      setUploading(false)
    }
  }

  const formatSize = (bytes) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="min-h-[calc(100vh-64px)] p-4 md:p-6">
      <div className="flex gap-6 max-w-[1400px] mx-auto items-start justify-center">
        {/* Job history sidebar - hidden during active upload */}
        {!uploading && (
          <div className="hidden lg:block flex-shrink-0">
            <JobHistory />
          </div>
        )}

        {/* Main upload content */}
        <div className="flex-1 flex items-center justify-center min-w-0">
          <div className="w-full max-w-2xl">
            {/* Header */}
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400 bg-clip-text text-transparent mb-3">
                Traffic Analytics
              </h1>
              <p className="text-gray-400 text-lg">Upload a video to analyze traffic patterns with AI</p>
            </div>

            {/* Upload card */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 md:p-8">
              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200
                  ${isDragActive ? 'border-emerald-400 bg-emerald-400/5' : ''}
                  ${isDragReject ? 'border-red-400 bg-red-400/5' : ''}
                  ${!isDragActive && !isDragReject ? 'border-gray-700 hover:border-gray-500 hover:bg-gray-800/30' : ''}
                  ${file ? 'border-emerald-500/50 bg-emerald-500/5' : ''}
                `}
              >
                <input {...getInputProps()} />

                {file ? (
                  <div className="space-y-4">
                    {preview && (
                      <div className="relative mx-auto w-full max-w-md rounded-lg overflow-hidden bg-black">
                        <video
                          ref={videoRef}
                          src={preview}
                          className="w-full aspect-video object-cover"
                          muted
                          onLoadedData={() => videoRef.current?.pause()}
                          autoPlay={false}
                        />
                      </div>
                    )}
                    <div className="flex items-center justify-center gap-3">
                      <Film size={18} className="text-emerald-400" />
                      <span className="text-white font-medium">{file.name}</span>
                      <span className="text-gray-500 text-sm">({formatSize(file.size)})</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); clearFile() }}
                        className="ml-2 p-1 rounded-full hover:bg-gray-800 text-gray-500 hover:text-white transition-colors"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="mx-auto w-14 h-14 rounded-full bg-gray-800 flex items-center justify-center">
                      <UploadIcon size={24} className={isDragActive ? 'text-emerald-400' : 'text-gray-500'} />
                    </div>
                    <div>
                      <p className="text-gray-300 font-medium">
                        {isDragActive ? 'Drop your video here' : 'Drop your video here or click to browse'}
                      </p>
                      <p className="text-gray-600 text-sm mt-1">.MP4, .MOV, .AVI — Max 500MB</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Error */}
              {error && (
                <div className="mt-4 flex items-center gap-2 text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
                  <AlertCircle size={16} />
                  <span className="text-sm">{error}</span>
                </div>
              )}

              {/* Upload progress */}
              {uploading && (
                <div className="mt-4">
                  <ProgressBar progress={uploadProgress} label="Uploading..." />
                </div>
              )}

              {/* Feature badges */}
              <div className="flex flex-wrap justify-center gap-3 mt-6">
                {features.map(({ icon: Icon, label, desc }) => (
                  <div key={label} className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/60 border border-gray-700/50 rounded-full">
                    <Icon size={14} className="text-emerald-500" />
                    <span className="text-xs text-gray-400">{label}</span>
                  </div>
                ))}
              </div>

              {/* Upload button */}
              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className={`mt-6 w-full py-3 rounded-xl font-semibold text-sm transition-all duration-200
                  ${!file || uploading
                    ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                    : 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-400 hover:to-teal-400 hover:shadow-lg hover:shadow-emerald-500/20 active:scale-[0.98]'
                  }`}
              >
                {uploading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    Uploading...
                  </span>
                ) : (
                  'Analyze Video'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
