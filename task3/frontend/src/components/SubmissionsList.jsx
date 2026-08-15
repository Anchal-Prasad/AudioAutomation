import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function SubmissionsList() {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/submissions`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const data = await res.json()
      setSubmissions(data)
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load submissions.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <p className="p-6 text-slate-500">Loading submissions…</p>
  if (error) return <p className="p-6 text-red-600">{error}</p>

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-slate-900">Submissions</h1>
        <button
          onClick={load}
          className="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 transition"
        >
          Refresh
        </button>
      </div>

      {submissions.length === 0 ? (
        <p className="text-slate-500">No submissions yet.</p>
      ) : (
        <div className="space-y-3">
          {submissions.map((s) => (
            <div key={s.id} className="border border-slate-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-slate-900">{s.submitted_name}</p>
                  <p className="text-sm text-slate-500">{s.submitted_phone}</p>
                </div>
                <p className="text-xs text-slate-400">
                  {new Date(s.submitted_at).toLocaleString()}
                </p>
              </div>

              <audio controls src={`${API_BASE}/audio/${s.file_path}`} className="w-full mb-3" />

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-sm">
                <Stat label="Duration" value={`${s.duration_sec}s`} />
                <Stat label="Sample rate" value={`${s.sample_rate_hz} Hz`} />
                <Stat label="Bitrate" value={`${s.bitrate_kbps} kbps`} />
                <Stat label="Loudness" value={s.loudness_db != null ? `${s.loudness_db} dB` : '—'} />
                <Stat label="Quality" value={s.quality_note} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-slate-50 rounded-md px-2 py-1.5">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-slate-800 font-medium">{value}</p>
    </div>
  )
}