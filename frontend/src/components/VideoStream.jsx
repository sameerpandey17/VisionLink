import { useRef } from 'react'

/**
 * VideoStream
 *
 * Renders the live face-detection stream by swapping an <img> src on every
 * binary WebSocket message. This is much simpler and more efficient than a
 * <video> element for MJPEG-style streams over WebSocket.
 *
 * Never queues frames — always displays the latest one. If the browser tab
 * goes to the background, visibilitychange is handled in the hook layer.
 */
export default function VideoStream({ frameSrc, onDimensions }) {
  const imgRef = useRef(null)

  function handleLoad() {
    if (imgRef.current && onDimensions) {
      onDimensions({
        width: imgRef.current.naturalWidth || imgRef.current.clientWidth,
        height: imgRef.current.naturalHeight || imgRef.current.clientHeight,
      })
    }
  }

  return (
    <img
      ref={imgRef}
      src={frameSrc || 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='}
      alt="Live face detection stream"
      className="stream-img"
      onLoad={handleLoad}
    />
  )
}
