"""
Mock camera publisher — generates synthetic frames and PUTs them to RMF RIO.

RIO schema:
  id:   unique identifier for this camera stream
  type: "<fleet>/<robot>/<camera_id>"  e.g. "tinyRobot/tinyBot_1/front"
  data: {
    "robot":      str,       # robot name
    "fleet":      str,       # fleet name
    "timestamp":  int,       # unix millis
    "encoding":   "jpeg",
    "base64":     str,       # base64-encoded JPEG
    "width":      int,
    "height":     int,
  }

Query from harness:
  GET /rios?type=tinyRobot/tinyBot_1/camera_front
  GET /rios?id=tinyRobot/tinyBot_1/camera_front
"""

import base64
import io
import time
import httpx
import jwt
from PIL import Image, ImageDraw, ImageFont
from rmf_config import RMF_BASE, JWT_TOKEN

ROBOT = "tinyBot_1"
FLEET = "tinyRobot"
CAMERA_ID = "camera_front"
RIO_TYPE = f"{FLEET}/{ROBOT}/{CAMERA_ID}"  # e.g. "tinyRobot/tinyBot_1/front"
RIO_ID = RIO_TYPE
PUBLISH_HZ = 1  # frames per second

def _make_token() -> str:
    return JWT_TOKEN

def _generate_frame(frame_num: int, robot: str) -> bytes:
    img = Image.new("RGB", (320, 240), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 310, 230], outline=(80, 80, 80), width=2)
    draw.text((20, 20), f"Robot: {robot}", fill=(200, 200, 200))
    draw.text((20, 50), f"Frame: {frame_num}", fill=(200, 200, 200))
    draw.text((20, 80), f"Time: {time.strftime('%H:%M:%S')}", fill=(200, 200, 200))
    # mock "scene" — moving box
    x = (frame_num * 5) % 260 + 20
    draw.rectangle([x, 140, x + 40, 180], fill=(0, 180, 100))
    draw.text((x, 185), "object", fill=(0, 180, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def publish_forever():
    headers = {"Authorization": f"Bearer {_make_token()}"}
    frame_num = 0
    print(f"Publishing camera frames to {RMF_BASE}/rios (type={RIO_TYPE})")
    print("Ctrl+C to stop.\n")
    with httpx.Client(headers=headers) as client:
        while True:
            jpeg = _generate_frame(frame_num, ROBOT)
            payload = {
                "id": RIO_ID,
                "type": RIO_TYPE,
                "data": {
                    "robot": ROBOT,
                    "fleet": FLEET,
                    "timestamp": int(time.time() * 1000),
                    "encoding": "jpeg",
                    "base64": base64.b64encode(jpeg).decode(),
                    "width": 320,
                    "height": 240,
                },
            }
            resp = client.put(f"{RMF_BASE}/rios", json=payload)
            print(f"frame {frame_num:04d}  type={RIO_TYPE}  status={resp.status_code}  size={len(jpeg)}B")
            frame_num += 1
            time.sleep(1.0 / PUBLISH_HZ)


if __name__ == "__main__":
    try:
        publish_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
