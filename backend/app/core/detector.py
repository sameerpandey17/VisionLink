import io
import logging
import math
from dataclasses import dataclass

import mediapipe as mp
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Single instance of FaceMesh initialized at startup
_face_mesh = None

@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    image_width: int
    image_height: int
    expression: str = "neutral"
    emoji: str = "😐"
    message: str = ""

# Expression Mappings
EXPRESSIONS = {
    "neutral":  {"emoji": "😐", "message": "I see you!"},
    "smile":    {"emoji": "☺️", "message": "Love that smile!"},
    "surprise": {"emoji": "😮", "message": "Whoa, what happened?"},
    "sad":      {"emoji": "☹️", "message": "Don't be sad, it's okay!"},
    "angry":    {"emoji": "😠", "message": "Did I do something wrong?"},
    "wink":     {"emoji": "😉", "message": "Feeling cheeky, are we?"},
}

def init_detector() -> None:
    """Initialise the MediaPipe FaceMesh model."""
    global _face_mesh
    try:
        _face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        logger.info("MediaPipe FaceMesh initialised.")
    except Exception as exc:
        raise RuntimeError(f"Failed to initialise MediaPipe FaceMesh: {exc}") from exc

def _dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

def classify_expression(landmarks) -> str:
    """
    Classify facial expression from FaceMesh landmarks.
    All distances are normalized by inter-eye distance (face_width).
    """
    # Face width (outer eye corners)
    face_width = _dist(landmarks[33], landmarks[263])
    if face_width < 1e-6:
        return "neutral"

    # Eye openness
    l_open = _dist(landmarks[159], landmarks[145]) / face_width
    r_open = _dist(landmarks[386], landmarks[374]) / face_width

    # Mouth openness
    mouth_open = _dist(landmarks[13], landmarks[14]) / face_width

    # Mouth width
    mouth_width = _dist(landmarks[61], landmarks[291]) / face_width

    # Brow-to-eye distance (lower = brows pushed down toward eye)
    l_brow_dist = _dist(landmarks[70],  landmarks[159]) / face_width
    r_brow_dist = _dist(landmarks[300], landmarks[386]) / face_width

    # Inner brow distance (lower = brows furrowed together)
    inner_brow_dist = _dist(landmarks[107], landmarks[336]) / face_width

    # Mouth corners relative to center
    mouth_center_y  = (landmarks[13].y + landmarks[14].y) / 2
    mouth_corners_y = (landmarks[61].y + landmarks[291].y) / 2
    frown_val = (mouth_corners_y - mouth_center_y) / face_width

    logger.debug(
        f"[METRICS] lb={l_brow_dist:.3f} rb={r_brow_dist:.3f} "
        f"ib={inner_brow_dist:.3f} mo={mouth_open:.3f} "
        f"mw={mouth_width:.3f} frown={frown_val:.3f}"
    )

    # Wink
    if l_open < 0.04 and r_open > 0.08:
        return "wink"
    if r_open < 0.04 and l_open > 0.08:
        return "wink"

    # Angry — brows pushed down OR pulled together
    # Threshold is very high (0.35) — triggers for any non-raised brow position
    if (l_brow_dist < 0.35 and r_brow_dist < 0.35) or inner_brow_dist < 0.35:
        return "angry"

    # Surprise — mouth open wide
    if mouth_open > 0.15:
        return "surprise"

    # Smile
    if mouth_width > 0.50 and frown_val < 0.00:
        return "smile"

    # Sad
    if frown_val > 0.025:
        return "sad"

    return "neutral"


def detect_face(frame_bytes: bytes) -> BoundingBox | None:
    """Run FaceMesh on a frame and return a BoundingBox with expression."""
    if _face_mesh is None:
        raise RuntimeError("Detector not initialised.")

    try:
        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
    except Exception:
        return None

    img_w, img_h = img.size
    rgb_array = np.array(img)
    results = _face_mesh.process(rgb_array)

    if not results.multi_face_landmarks:
        return None

    face_landmarks = results.multi_face_landmarks[0].landmark

    # Bounding box from all landmark positions
    x_coords = [p.x for p in face_landmarks]
    y_coords = [p.y for p in face_landmarks]
    xmin, xmax = min(x_coords), max(x_coords)
    ymin, ymax = min(y_coords), max(y_coords)

    x = int(xmin * img_w)
    y = int(ymin * img_h)
    w = int((xmax - xmin) * img_w)
    h = int((ymax - ymin) * img_h)

    expr_key = classify_expression(face_landmarks)
    expr_data = EXPRESSIONS.get(expr_key, EXPRESSIONS["neutral"])

    return BoundingBox(
        x=max(0, x),
        y=max(0, y),
        width=min(w, img_w - x),
        height=min(h, img_h - y),
        confidence=0.9,
        image_width=img_w,
        image_height=img_h,
        expression=expr_key,
        emoji=expr_data["emoji"],
        message=expr_data["message"],
    )
