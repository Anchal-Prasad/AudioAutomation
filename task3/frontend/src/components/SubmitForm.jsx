import { useState, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

export default function SubmitForm() {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [audioBlob, setAudioBlob] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [isRecording, setIsRecording] = useState(false)
  const [status, setStatus] = useState(null) // null | 'submitting' | 'success' | 'error'
  const [statusMessage, setStatusMessage] = useState('')
  const [lastResult, setLastResult] = useState(null)

  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach((track) => track.stop())
      }

      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch (err) {
      setStatus('error')
      setStatusMessage('Could not access microphone. Check browser permissions, or use file upload instead.')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAudioBlob(file)
    setAudioUrl(URL.createObjectURL(file))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !phone.trim() || !audioBlob) {
      setStatus('error')
      setStatusMessage('Name, phone, and an audio recording or file are all required.')
      return
    }

    setStatus('submitting')
    setStatusMessage('')

    const formData = new FormData()
    formData.append('name', name.trim())
    formData.append('phone', phone.trim())
    const filename = audioBlob.name || 'recording.webm'
    formData.append('audio', audioBlob, filename)

    try {
      const res = await fetch(`${API_BASE}/submissions`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server returned ${res.status}`)
      }
      const data = await res.json()
      setLastResult(data)
      setStatus('success')
      setStatusMessage('Submitted. Properties extracted below.')
      setName('')
      setPhone('')
      setAudioBlob(null)
      setAudioUrl(null)
    } catch (err) {
      setStatus('error')
      setStatusMessage(err.message || 'Submission failed.')
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      <h1 className="text-2xl font-semibold text-slate-900 mb-1">Submit a recording</h1>
      <p className="text-slate-500 mb-6 text-sm">
        Record audio in your browser or upload a file. We'll extract its properties automatically.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-900"
            placeholder="Your full name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Phone number</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-900"
            placeholder="9876543210"
          />
        </div>

        <div className="border border-dashed border-slate-300 rounded-lg p-5">
          <p className="text-sm font-medium text-slate-700 mb-3">Audio</p>

          <div className="flex items-center gap-3 mb-3">
            {!isRecording ? (
              <button
                type="button"
                onClick={startRecording}
                className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-700 transition"
              >
                ● Start recording
              </button>
            ) : (
              <button
                type="button"
                onClick={stopRecording}
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition animate-pulse"
              >
                ■ Stop recording
              </button>
            )}
            <span className="text-slate-400 text-sm">or</span>
            <label className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer transition">
              Upload file
              <input type="file" accept="audio/*" onChange={handleFileChange} className="hidden" />
            </label>
          </div>

          {audioUrl && (
            <audio controls src={audioUrl} className="w-full mt-2" />
          )}
        </div>

        <button
          type="submit"
          disabled={status === 'submitting'}
          className="w-full py-2.5 rounded-lg bg-slate-900 text-white font-medium hover:bg-slate-700 disabled:opacity-50 transition"
        >
          {status === 'submitting' ? 'Submitting…' : 'Submit'}
        </button>

        {status === 'error' && (
          <p className="text-red-600 text-sm">{statusMessage}</p>
        )}
        {status === 'success' && (
          <div className="text-sm bg-green-50 border border-green-200 rounded-lg p-4 space-y-1">
            <p className="text-green-700 font-medium">{statusMessage}</p>
            <p>Duration: {lastResult.duration_sec}s</p>
            <p>Sample rate: {lastResult.sample_rate_hz} Hz</p>
            <p>Bitrate: {lastResult.bitrate_kbps} kbps</p>
            <p>Loudness: {lastResult.loudness_db ?? '—'} dB</p>
            <p>Quality: {lastResult.quality_note}</p>
          </div>
        )}
      </form>
    </div>
  )
}