import io

from PIL import Image, ImageDraw

from app.core.detector import BoundingBox


def draw_roi(
    frame_bytes: bytes,
    box: BoundingBox,
    outline: tuple[int, int, int] = (0, 255, 0),
    line_width: int = 2,
) -> bytes:
    """
    Draw a bounding-box rectangle on the frame using Pillow (no OpenCV).

    Args:
        frame_bytes: Raw JPEG or PNG bytes of the original frame.
        box:         The detected face bounding box.
        outline:     RGB colour for the rectangle. Default: green.
        line_width:  Stroke width in pixels.

    Returns:
        JPEG bytes of the rendered frame with the ROI drawn.
    """
    img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [box.x, box.y, box.x + box.width, box.y + box.height],
        outline=outline,
        width=line_width,
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
