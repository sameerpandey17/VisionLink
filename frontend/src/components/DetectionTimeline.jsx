import { useState, useEffect } from 'react'

export default function DetectionTimeline({ latestDetection }) {
  const [history, setHistory] = useState([])

  // Initial load — latest 10 only
  useEffect(() => {
    fetch('/api/roi?limit=10')
      .then(r => r.json())
      .then(d => setHistory(d.detections || []))
      .catch(console.error)
  }, [])

  // Prepend new detection, keep max 10
  useEffect(() => {
    if (!latestDetection) return
    setHistory(prev => {
      if (prev.length > 0 && prev[0].id === latestDetection.id) return prev
      return [latestDetection, ...prev].slice(0, 10)
    })
  }, [latestDetection])

  const fmt = (ts) =>
    new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <>
      <div className="panel-header">
        <div className="panel-title">Detection Log</div>
        <div className="panel-badge">Latest 10</div>
      </div>

      <div className="log-list">
        {history.length === 0 && (
          <div className="log-empty">
            Awaiting detections...<br />
            <span style={{ fontSize: '0.6875rem', marginTop: '0.25rem', display: 'block' }}>
              Initialize Vision to begin
            </span>
          </div>
        )}

        {history.map((det, idx) => (
          <div key={det.id || idx} className="log-item">
            <div className="log-emoji">
              {det.emoji || '👤'}
            </div>
            <div className="log-info">
              <div className="log-expr">{det.expression || 'Face'} detected</div>
              <div className="log-time">{fmt(det.timestamp)}</div>
              <div className="log-bar-wrap">
                <div
                  className="log-bar-fill"
                  style={{ width: `${(det.confidence || 0) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
