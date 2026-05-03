/**
 * StatsPanel
 *
 * Displays live stream statistics: connection status, frames received, and
 * a derived FPS estimate. Purely presentational — all data comes from props.
 */
export default function StatsPanel({ status, frameCount }) {
  return (
    <div className="stats-panel" role="status" aria-live="polite">
      <div className="stat">
        <span className="stat-label">Connection</span>
        <span className="stat-value" style={{ color: status === 'connected' ? '#22c55e' : '#ef4444' }}>
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      </div>
      <div className="stat">
        <span className="stat-label">Frames received</span>
        <span className="stat-value">{frameCount.toLocaleString()}</span>
      </div>
      <div className="stat">
        <span className="stat-label">Stream source</span>
        <span className="stat-value" style={{ fontSize: '0.9rem', color: '#94a3b8' }}>
          /stream
        </span>
      </div>
    </div>
  )
}
