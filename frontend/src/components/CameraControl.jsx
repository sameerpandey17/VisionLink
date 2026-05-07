import { useState, useRef, useEffect } from 'react';

export default function CameraControl({ onStatusChange }) {
  const [isRecording, setIsRecording] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const loopRef = useRef(null);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play(); // Explicitly start playback
      }
      streamRef.current = stream;
      setIsRecording(true);
      onStatusChange && onStatusChange('Transmitting...');
      
      // Start ingestion loop
      loopRef.current = setInterval(sendFrame, 100); // 10 FPS
    } catch (err) {
      console.error("Error accessing camera:", err);
      alert("Could not access camera. Please allow permissions.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    setIsRecording(false);
    clearInterval(loopRef.current);
    onStatusChange && onStatusChange('Stopped');
  };

  const sendFrame = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      canvas.toBlob(async (blob) => {
        if (!blob) return;
        
        const formData = new FormData();
        formData.append('frame', blob, 'camera_frame.jpg');
        
        try {
          const res = await fetch('/ingest', {
            method: 'POST',
            body: formData
          });
          if (!res.ok) {
            console.error("Ingest failed:", res.statusText);
          }
        } catch (err) {
          console.error("Error sending frame:", err);
        }
      }, 'image/jpeg', 0.8);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  return (
    <div className="card" style={{ marginTop: '1rem' }}>
      <h2 className="card-title">Camera Ingestion</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Visible preview for local feedback */}
        <div style={{ 
          width: '100%', 
          height: isRecording ? '120px' : '0', 
          background: '#000', 
          borderRadius: '8px', 
          overflow: 'hidden',
          transition: 'height 0.3s ease',
          position: 'relative'
        }}>
          <video 
            ref={videoRef} 
            autoPlay 
            playsInline 
            muted 
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
          />
          {isRecording && (
            <div style={{ 
              position: 'absolute', 
              top: '8px', 
              right: '8px', 
              width: '8px', 
              height: '8px', 
              background: '#ef4444', 
              borderRadius: '50%',
              boxShadow: '0 0 8px #ef4444'
            }} />
          )}
        </div>

        <button 
          onClick={isRecording ? stopCamera : startCamera}
          style={{
            padding: '0.75rem',
            backgroundColor: isRecording ? '#ef4444' : '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '600',
            transition: 'background-color 0.2s'
          }}
        >
          {isRecording ? 'Stop Camera' : 'Start Camera'}
        </button>
        
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        
        {isRecording && (
          <div style={{ fontSize: '0.75rem', color: '#64748b', textAlign: 'center' }}>
            Broadcasting 10 FPS to system
          </div>
        )}
      </div>
    </div>
  );
}
