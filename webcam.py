import os
import time
import cv2
import torch
import requests
import threading
from collections import defaultdict
import function.utils_rotate as utils_rotate
import function.helper as helper

# ================= CONFIG =================
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DET_SIZE = 640
OCR_CONF = 0.60

SERVER_STREAM_URL = "http://192.168.1.184:8000/api/stream/raspberrypi_cam"
DJANGO_API_URL = "http://192.168.1.184:8000/api/upload/"
SOURCE_NAME = "raspberrypi_cam"

SEND_COOLDOWN_SEC = 5
REQUEST_TIMEOUT_SEC = 5
STREAM_INTERVAL = 0.05  # ~20 FPS
# ==========================================


def open_camera(index=0, w=640, h=480):
    """Mở camera, ưu tiên driver V4L2."""
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def encode_jpg_bytes(bgr_img, quality=85):
    """Chuyển ảnh sang bytes JPG."""
    ok, buf = cv2.imencode(".jpg", bgr_img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf.tobytes() if ok else None


def create_django_session():
    """Tạo session giữ kết nối lâu dài đến Django."""
    session = requests.Session()
    session.headers.update({"User-Agent": "LP-Client-RaspberryPi"})
    print(f"🌐 Connected to Django: {DJANGO_API_URL}")
    return session


def send_to_django(session, plate, conf, crop):
    """Gửi dữ liệu qua session (không tạo lại kết nối)."""
    data = {"plate": plate, "confidence": f"{conf:.2f}", "source": SOURCE_NAME}
    jpg = encode_jpg_bytes(crop, 85)
    files = {"image": ("crop.jpg", jpg, "image/jpeg")} if jpg else None
    try:
        r = session.post(DJANGO_API_URL, data=data, files=files, timeout=REQUEST_TIMEOUT_SEC)
        print(f"[UPLOAD] {plate} ({conf:.2f}) -> {r.status_code}")
    except requests.exceptions.RequestException as e:
def load_models():
    """Tải model YOLO detect + OCR."""
    print("Loading YOLOv5 models...")
    det = torch.hub.load('ultralytics/yolov5', 'custom', path='model/LP_detector_nano_61.pt',
                         force_reload=False, verbose=False)
    ocr = torch.hub.load('ultralytics/yolov5', 'custom', path='model/LP_ocr_nano_62.pt',
                         force_reload=False, verbose=False)
    ocr.conf = OCR_CONF
    return det, ocr


# ===========================================================
# STREAMING THREAD
# ===========================================================
def stream_thread_func(cap):
    """Luồng gửi video MJPEG lên server."""
    print(f"🎥 Starting MJPEG stream to {SERVER_STREAM_URL}")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        jpg = encode_jpg_bytes(frame, 80)
        if not jpg:
            continue
        try:
            requests.post(SERVER_STREAM_URL, data=jpg, timeout=1)
        except Exception:
            pass
        time.sleep(STREAM_INTERVAL)


# ===========================================================
# MAIN DETECTION LOOP
# ===========================================================
def main():
    session = create_django_session()

    cap = open_camera(CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT)
    if not cap.isOpened():
        print("❌ Camera not found.")
        return

    # Tải model
    yolo_det, yolo_ocr = load_models()
    last_sent = defaultdict(float)

    # Khởi động luồng stream
    threading.Thread(target=stream_thread_func, args=(cap,), daemon=True).start()

    print("🚗 Running detection + upload + stream...")
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        try:
            results = yolo_det(frame, size=DET_SIZE)
        except Exception as e:
            print("Detection failed:", e)
            time.sleep(1)
            continue

        df = results.pandas().xyxy[0]
        for _, row in df.iterrows():
            x1, y1, x2, y2 = map(int, [row.xmin, row.ymin, row.xmax, row.ymax])
            crop = frame[y1:y2, x1:x2]
            plate = helper.read_plate(yolo_ocr, utils_rotate.deskew(crop, 0, 0))

            if plate and plate != "unknown":
                now = time.time()
                if now - last_sent[plate] >= SEND_COOLDOWN_SEC:
                    send_to_django(session, plate, row.confidence, crop)
                    last_sent[plate] = now
                else:
                    remain = int(SEND_COOLDOWN_SEC - (now - last_sent[plate]))
                    print(f"⏳ Skip {plate}, wait {remain}s")


if __name__ == "__main__":
    main()

