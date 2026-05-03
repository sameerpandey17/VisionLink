import { useEffect, useRef } from 'react'

const POLL_INTERVAL_MS = 500

/**
 * RoiCanvas
 *
 * Draws ROI bounding boxes on a canvas overlay using data from GET /api/roi.
 * Independent from the video stream — uses its own polling loop so the two
 * can diverge without one blocking the other.
 */
export default function RoiCanvas({ dimensions, latestBox, onBoxFetched }) {
  const canvasRef = useRef(null)

  // Poll /api/roi at a fixed interval
  useEffect(() => {
    let alive = true

    async function poll() {
      try {
        const resp = await fetch('/api/roi?limit=1')
        if (!resp.ok) return
        const data = await resp.json()
        if (data.detections?.length > 0 && alive) {
          onBoxFetched(data.detections[0])
        }
      } catch {
        // Network error — silently skip this poll cycle
      }
    }

    const id = setInterval(poll, POLL_INTERVAL_MS)
    poll()

    return () => {
      alive = false
      clearInterval(id)
    }
  }, [onBoxFetched])

  // Redraw canvas whenever the box changes
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

    ctx.strokeStyle = 'rgba(34, 197, 94, 0.9)'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, w, h)

    // Confidence label
    ctx.fillStyle = 'rgba(34, 197, 94, 0.85)'
    ctx.fillRect(x, y - 20, 80, 20)
    ctx.fillStyle = '#000'
    ctx.font = '12px monospace'
    ctx.fillText(`${(latestBox.confidence * 100).toFixed(1)}%`, x + 4, y - 5)
  }, [latestBox, dimensions])

  return (
    <canvas
      ref={canvasRef}
      className="canvas-overlay"
      width={dimensions.width || 640}
      height={dimensions.height || 480}
    />
  )
}
