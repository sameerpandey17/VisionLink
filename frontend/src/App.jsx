import { useState } from 'react'
import VideoStream from './components/VideoStream.jsx'
import RoiCanvas from './components/RoiCanvas.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import useWebSocket from './hooks/useWebSocket.js'

export default function App() {
  const { frameSrc, status, frameCount } = useWebSocket('/stream')
  const [imgDimensions, setImgDimensions] = useState({ width: 640, height: 480 })
  const [latestBox, setLatestBox] = useState(null)

  return (
    <div className="app">
      <header className="header">
        <div className={`dot ${status !== 'connected' ? 'disconnected' : ''}`} />
        <h1>Face Detection Stream</h1>
        <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
          {status === 'connected' ? 'Live' : status === 'reconnecting' ? 'Reconnecting…' : 'Disconnected'}
        </span>
      </header>

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
        {status !== 'connected' && (
          <div className="status-banner">{status === 'reconnecting' ? '⟳ Reconnecting…' : '✕ Disconnected'}</div>
        )}
      </div>

      <StatsPanel status={status} frameCount={frameCount} />
    </div>
  )
}
