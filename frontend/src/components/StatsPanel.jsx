/**
 * StatsPanel
 *
 * Displays live stream statistics in a sleek vertical grid.
 */
export default function StatsPanel({ status, frameCount }) {
  return (
    <div className="card" role="status" aria-live="polite">
      <h2 className="card-title">System Metrics</h2>
      <div className="stats-grid">
        <div className="stat-item">
          <span className="stat-label">Connection State</span>
          <span className="stat-value" style={{ color: status === 'connected' ? 'var(--success)' : 'var(--error)' }}>
            {status.toUpperCase()}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Total Frames</span>
          <span className="stat-value">{frameCount.toLocaleString()}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Stream Source</span>
          <span className="stat-value" style={{ fontSize: '1rem', color: 'var(--accent-primary)' }}>
            WebSocket
          </span>
        </div>
      </div>
    </div>
  )
}
