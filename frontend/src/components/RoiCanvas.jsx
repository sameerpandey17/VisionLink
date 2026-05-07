import { useEffect, useRef } from 'react'

const POLL_INTERVAL_MS = 250


export default function RoiCanvas({ dimensions, latestBox, onBoxFetched }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    let alive = true
    async function poll() {
      try {
        const resp = await fetch('/api/roi?limit=1')
        if (!resp.ok) return
        const data = await resp.json()
        if (data.detections?.length > 0 && alive) {
          const latest = data.detections[0]
          
          // Staleness check: If detection is older than 5 seconds, it's a ghost from a previous session
          const detectionTime = new Date(latest.timestamp).getTime()
          const now = Date.now()
          
          if (now - detectionTime < 5000) {
            onBoxFetched(latest)
          } else {
            onBoxFetched(null)
          }
        } else if (alive) {
          onBoxFetched(null)
        }
      } catch {
        // Silently skip
      }
    }

    const id = setInterval(poll, POLL_INTERVAL_MS)
    poll()
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [onBoxFetched])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!latestBox) return

    const scaleX = canvas.width / (dimensions.width || 640)
    const scaleY = canvas.height / (dimensions.height || 480)

    const x = latestBox.x * scaleX
    const y = latestBox.y * scaleY
    const w = latestBox.width * scaleX
    const h = latestBox.height * scaleY

    // Draw main box with a glow effect
    ctx.shadowBlur = 10
    ctx.shadowColor = latestBox.expression === 'angry' ? 'rgba(255, 75, 75, 0.5)' : 'rgba(30, 201, 153, 0.5)'
    ctx.strokeStyle = latestBox.expression === 'angry' ? '#FF4B4B' : '#1EC999'
    ctx.lineWidth = 3
    ctx.strokeRect(x, y, w, h)
    
    // Corners
    const cornerLen = 15
    ctx.lineWidth = 5
    ctx.shadowBlur = 0
    
    // Corner drawing...
    const drawCorner = (px, py, dx, dy) => {
      ctx.beginPath()
      ctx.moveTo(px, py + (dy * cornerLen))
      ctx.lineTo(px, py)
      ctx.lineTo(px + (dx * cornerLen), py)
      ctx.stroke()
    }
    
    drawCorner(x, y, 1, 1) // Top Left
    drawCorner(x + w, y, -1, 1) // Top Right
    drawCorner(x, y + h, 1, -1) // Bottom Left
    drawCorner(x + w, y + h, -1, -1) // Bottom Right

    // (Emoji and Message HUD moved to DOM in App.jsx)

    // Confidence Label
    const label = `${(latestBox.confidence * 100).toFixed(1)}% CONFIDENCE`
    ctx.font = 'bold 9px "JetBrains Mono"'
    const textWidth = ctx.measureText(label).width
    
    ctx.fillStyle = latestBox.expression === 'angry' ? '#FF4B4B' : '#1EC999'
    ctx.fillRect(x, y - 20, textWidth + 12, 20)
    
    ctx.fillStyle = '#1A1A2E'
    ctx.fillText(label, x + 6, y - 7)
  }, [latestBox, dimensions])

  return (
    <canvas
      ref={canvasRef}
      className="canvas-layer"
      width={dimensions.width || 640}
      height={dimensions.height || 480}
    />
  )
}
