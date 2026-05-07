import { useState, useRef, useEffect } from 'react'

export default function CameraControl() {
  const [isRecording, setIsRecording] = useState(false)
  const [fps, setFps] = useState(0)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const loopRef = useRef(false)
  const lastFrameTime = useRef(Date.now())

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, frameRate: { ideal: 30 } }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      streamRef.current = stream
      loopRef.current = true
      setIsRecording(true)
      transmitLoop()
    } catch (err) {
      console.error('Camera error:', err)
    }
  }

  const stopCamera = () => {
    loopRef.current = false
    streamRef.current?.getTracks().forEach(t => t.stop())
    setIsRecording(false)
    setFps(0)
  }

  const transmitLoop = async () => {
    if (!loopRef.current) return
    const t0 = Date.now()
    await sendFrame()
    setTimeout(transmitLoop, Math.max(0, 100 - (Date.now() - t0)))
  }

  const sendFrame = async () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || video.readyState < 2) return
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.8))
    if (!blob) return
    const form = new FormData()
    form.append('frame', blob, 'frame.jpg')
    try {
      await fetch('/api/ingest', { method: 'POST', body: form })
      const now = Date.now()
      setFps(Math.round(1000 / (now - lastFrameTime.current)))
      lastFrameTime.current = now
    } catch { /* network hiccup, skip */ }
  }

  useEffect(() => () => stopCamera(), [])

  return (
    <>
      <div className="card-label">
        Vision Input
        {isRecording && (
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '0.625rem',
            color: 'var(--pink)',
            fontWeight: 700,
            letterSpacing: '0.06em'
          }}>
            {fps} FPS
          </span>
        )}
      </div>

      {/* Preview */}
      <div className={`camera-preview ${isRecording ? 'recording' : ''}`}>
        {!isRecording && <div className="camera-standby">SENSOR STANDBY</div>}

        <video
          ref={videoRef}
          autoPlay playsInline muted
          style={{
            width: '100%',
            display: isRecording ? 'block' : 'none',
            height: '150px',
            objectFit: 'cover',
          }}
        />
        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {isRecording && (
          <div className="live-tag">
            <span style={{
              width: 5, height: 5,
              borderRadius: '50%',
              background: 'var(--pink)',
              display: 'inline-block',
              animation: 'blink 1s step-end infinite'
            }} />
            LIVE
          </div>
        )}
      </div>

      <button
        className={`btn ${isRecording ? 'btn-danger' : 'btn-primary'}`}
        onClick={isRecording ? stopCamera : startCamera}
      >
        {isRecording ? '⏹ Terminate Stream' : '▶ Initialize Vision'}
      </button>
    </>
  )
}
