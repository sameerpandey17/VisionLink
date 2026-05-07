import { useState, useCallback, useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import useWebSocket from './hooks/useWebSocket'
import VideoStream from './components/VideoStream'
import RoiCanvas from './components/RoiCanvas'
import DetectionTimeline from './components/DetectionTimeline'
import CameraControl from './components/CameraControl'

export default function App() {
  const { frameSrc, status, frameCount } = useWebSocket('/api/stream')
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [latestDetection, setLatestDetection] = useState(null)
  const shellRef = useRef(null)

  const handleBoxFetched = useCallback((det) => setLatestDetection(det), [])
  const isAngry = latestDetection?.expression === 'angry'
  const isOnline = status === 'connected'

  // Entry animation
  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.app-header',
        { opacity: 0, y: -16 },
        { opacity: 1, y: 0, duration: 0.55, ease: 'power3.out' }
      )
      gsap.fromTo('.sidebar',
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.55, delay: 0.1, ease: 'power3.out' }
      )
      gsap.fromTo('.stat-card',
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.45, stagger: 0.08, delay: 0.15, ease: 'power3.out' }
      )
      gsap.fromTo('.stream-wrapper',
        { opacity: 0, scale: 0.99 },
        { opacity: 1, scale: 1, duration: 0.5, delay: 0.25, ease: 'power3.out' }
      )
      gsap.fromTo('.right-panel',
        { opacity: 0, x: 16 },
        { opacity: 1, x: 0, duration: 0.5, delay: 0.3, ease: 'power3.out' }
      )
    }, shellRef)
    return () => ctx.revert()
  }, [])

  // Subtle pulse on expression change
  useEffect(() => {
    if (!latestDetection?.expression) return
    gsap.fromTo('.stream-wrapper',
      { scale: 1 },
      { scale: 1.003, duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.inOut' }
    )
  }, [latestDetection?.expression])

  return (
    <div className="app-shell" ref={shellRef}>

      {/* ── TOP HEADER ── */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-dot" />
          <span className="brand-name">VisionLink</span>
          <span className="brand-sub">Neural Vision System</span>
        </div>

        <div className={`system-pill ${isOnline ? 'online' : ''}`}>
          <div className="pill-dot" style={{ color: isOnline ? '#0A9078' : '#9AA3B2' }} />
          {isOnline ? 'System Optimal' : 'Connecting...'}
        </div>
      </header>

      {/* ── BODY ── */}
      <div className="app-body">

        {/* LEFT SIDEBAR */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="sidebar-brand-title">VisionLink</div>
            <div className="sidebar-brand-sub">Vision System</div>
            <div className="engine-badge">
              <div className="dot" />
              Engine Active
            </div>
          </div>

          <div className="sidebar-divider" />

          <div className="nav-item active">
            {/* Monitor icon */}
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/>
              <path d="M8 21h8M12 17v4"/>
            </svg>
            Live Monitor
          </div>

          <div className="nav-item">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            Detection Log
          </div>
        </aside>

        {/* MAIN CONTENT */}
        <main className="main-content">

          {/* Stat Cards */}
          <div className="stats-row">
            <div className="stat-card accent-teal">
              <div className="stat-label">Engine Status</div>
              <div className={`stat-value ${isOnline ? 'teal' : ''}`}>
                {isOnline ? 'OPTIMAL' : 'OFFLINE'}
              </div>
              <div className="stat-sub">MediaPipe FaceMesh</div>
            </div>

            <div className="stat-card accent-sky">
              <div className="stat-label">Frames Processed</div>
              <div className="stat-value sky">{frameCount.toLocaleString()}</div>
              <div className="stat-sub">This session</div>
            </div>

            <div className="stat-card accent-pink">
              <div className="stat-label">Current Expression</div>
              <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                {latestDetection?.emoji || '—'}&nbsp;
                <span style={{ fontFamily: 'Sora', fontSize: '1rem', fontWeight: 600, color: 'var(--text-2)', textTransform: 'capitalize' }}>
                  {latestDetection?.expression || 'Awaiting...'}
                </span>
              </div>
              <div className="stat-sub">{latestDetection?.message || 'No face detected'}</div>
            </div>
          </div>

          {/* Video Stream */}
          <div className="stream-section">
            <div className={`stream-wrapper ${isAngry ? 'angry-state' : ''}`}>
              <VideoStream frameSrc={frameSrc} onDimensions={setDimensions} />
              <RoiCanvas dimensions={dimensions} latestBox={latestDetection} onBoxFetched={handleBoxFetched} />

              {/* Corner brackets */}
              <div className="corner tl" /><div className="corner tr" />
              <div className="corner bl" /><div className="corner br" />

              {/* HUD */}
              <div className="stream-hud">
                <div className="hud-chip">
                  <div className="live-dot" />
                  ENCRYPTED FEED
                </div>

                {latestDetection?.emoji && (
                  <div className="emotion-bubble">
                    <div className="emotion-emoji">{latestDetection.emoji}</div>
                    <div className="emotion-expr">{latestDetection.expression}</div>
                    <div className="emotion-msg">{latestDetection.message}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Bottom Row */}
          <div className="bottom-row">
            <div className="card">
              <CameraControl />
            </div>

            <div className="card">
              <div className="card-label">Neural Engine</div>
              <div className="engine-card-body">
                <div className="engine-icon">⚡</div>
                <div>
                  <div className="engine-info-title">Active & Optimized</div>
                  <div className="engine-info-sub">468 landmark real-time analysis</div>
                  <div className="engine-stat">
                    <div className="engine-stat-dot" />
                    &lt;10ms inference latency
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* RIGHT PANEL */}
        <aside className="right-panel">
          <DetectionTimeline latestDetection={latestDetection} />
        </aside>

      </div>
    </div>
  )
}
