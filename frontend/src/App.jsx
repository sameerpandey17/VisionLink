import { useState, useEffect } from 'react'
import VideoStream from './components/VideoStream.jsx'
import RoiCanvas from './components/RoiCanvas.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import useWebSocket from './hooks/useWebSocket.js'
import CameraControl from './components/CameraControl.jsx'
export default function App() {
  const { frameSrc, status, frameCount } = useWebSocket('/stream')
  const [imgDimensions, setImgDimensions] = useState({ width: 1280, height: 720 })
  const [latestBox, setLatestBox] = useState(null)
  const [logs, setLogs] = useState([])

  // Add a log entry when a face is detected
  useEffect(() => {
    if (latestBox) {
      const time = new Date().toLocaleTimeString()
      setLogs(prev => [{ id: Date.now(), time, msg: `Face detected (${(latestBox.confidence * 100).toFixed(0)}%)` }, ...prev].slice(0, 50))
    }
  }, [latestBox])

  return (
    <div className="app">
      <header className="header">
        <div className="header-title">
          <div className="dot" style={{ backgroundColor: status === 'connected' ? '#22c55e' : '#ef4444' }} />
          <h1>Face Detection Stream</h1>
        </div>
        <div className="status-indicator">
          {status === 'connected' ? 'LIVE SESSION' : 'SYSTEM OFFLINE'}
          <span style={{ marginLeft: '1rem', color: '#64748b' }}>{status.toUpperCase()}</span>
        </div>
      </header>

      <main className="main-content">
        <div className="stream-container">
          <VideoStream
            frameSrc={frameSrc}
            onDimensions={setImgDimensions}
          />
          <RoiCanvas
            dimensions={imgDimensions}
            latestBox={latestBox}
            onBoxFetched={setLatestBox}
          />
        </div>
      </main>

      <aside className="sidebar">
        <StatsPanel status={status} frameCount={frameCount} />
        
        <CameraControl />

        <div className="card" style={{ marginTop: '1rem' }}>
          <h2 className="card-title">Live Activity</h2>
          <div className="log-container">
            {logs.length === 0 ? (
              <div style={{ color: '#64748b', fontSize: '0.875rem', textAlign: 'center', padding: '1rem' }}>
                Waiting for detections...
              </div>
            ) : (
              logs.map(log => (
                <div key={log.id} className="log-entry">
                  <span className="log-time">[{log.time}]</span>
                  <span className="log-msg">{log.msg}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>
    </div>
  )
}
