import io
import logging
from dataclasses import dataclass

import mediapipe as mp

logger = logging.getLogger(__name__)

_detector = None  # Initialised once at startup


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    image_width: int
    image_height: int


def init_detector() -> None:
    """Initialise the MediaPipe face detection model. Call once at startup."""
    global _detector
    try:
        _detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,  # 0 = short-range, faster
            min_detection_confidence=0.5,
        )
        logger.info("MediaPipe face detector initialised.")
    except Exception as exc:
        raise RuntimeError(f"Failed to initialise MediaPipe detector: {exc}") from exc


def detect_face(frame_bytes: bytes) -> BoundingBox | None:
    """
    Run face detection on a single frame.

    Returns the highest-confidence BoundingBox, or None if no face is found.
    Never raises — a frame with no face is a normal operating condition.
    """
    if _detector is None:
        raise RuntimeError("Detector not initialised. Call init_detector() at startup.")

    from PIL import Image

    try:
        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
    except Exception:
        logger.warning("detect_face: could not decode frame bytes as image.")
        return None

    img_w, img_h = img.size
    import numpy as np

    rgb_array = np.array(img)

    results = _detector.process(rgb_array)

    if not results.detections:
        return None

    if len(results.detections) > 1:
        logger.warning("Multiple faces detected (%d); using highest-confidence.", len(results.detections))

    best = max(results.detections, key=lambda d: d.score[0])
    score = best.score[0]

    bb = best.location_data.relative_bounding_box
    x = int(bb.xmin * img_w)
    y = int(bb.ymin * img_h)
    w = int(bb.width * img_w)
    h = int(bb.height * img_h)

    # Clamp to image bounds
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))

    return BoundingBox(
        x=x,
        y=y,
        width=w,
        height=h,
        confidence=float(score),
        image_width=img_w,
        image_height=img_h,
    )
