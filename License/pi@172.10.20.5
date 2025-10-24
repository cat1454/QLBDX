from PIL import Image
import cv2
import torch
import math
import numpy as np
import function.utils_rotate as utils_rotate
from IPython.display import display
import os
import time
import argparse
import function.helper as helper

# =============== CONFIG ===============
DET_SIZE = 640            # input size cho detector
OCR_CONF = 0.50           # nới nhẹ so với 0.60 để “bắt” ký tự trắng mảnh
USE_CAMERA_INDEX = 0      # 0 = webcam mặc định
SHOW_FPS = True
# =====================================

# --- Load models ---
yolo_LP_detect = torch.hub.load(
    'yolov5', 'custom',
    path='model/LP_detector_nano_61.pt',
    force_reload=True, source='local'
)
yolo_license_plate = torch.hub.load(
    'yolov5', 'custom',
    path='model/LP_ocr_nano_62.pt',
    force_reload=True, source='local'
)
yolo_license_plate.conf = OCR_CONF

# -------- Tiền xử lý để đọc chữ trắng/đen tốt hơn --------
def pad_and_resize(img_bgr, out_h=256, pad_ratio=0.10):
    h, w = img_bgr.shape[:2]
    pad = int(pad_ratio * max(h, w))
    img2 = cv2.copyMakeBorder(img_bgr, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    ratio = out_h / img2.shape[0]
    out_w = int(img2.shape[1] * ratio)
    return cv2.resize(img2, (out_w, out_h), interpolation=cv2.INTER_CUBIC)

def preprocess_variants(img_bgr):
    """
    Tạo nhiều phiên bản của crop để OCR:
    - gốc
    - CLAHE (tăng tương phản cục bộ)
    - Adaptive Threshold (nhị phân)
    - Đảo màu (hữu ích khi chữ trắng trên nền tối)
    - Adaptive rồi đảo
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1) Giữ nguyên
    v1 = img_bgr

    # 2) CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    v2g = clahe.apply(gray)

    # 3) Adaptive threshold (Gaussian)
    v3g = cv2.adaptiveThreshold(
        v2g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )

    # 4) Đảo màu grayscale
    v4g = cv2.bitwise_not(gray)

    # 5) Adaptive rồi đảo
    v5g = cv2.bitwise_not(v3g)

    def to3(x):
        return cv2.cvtColor(x, cv2.COLOR_GRAY2BGR) if len(x.shape) == 2 else x

    return [to3(v) for v in [v1, v2g, v3g, v4g, v5g]]

# --- Video source ---
vid = cv2.VideoCapture(USE_CAMERA_INDEX)
# Mẹo: Nếu bị lóa, có thể thử chỉnh các thuộc tính sau (tùy driver hỗ trợ)
# vid.set(cv2.CAP_PROP_EXPOSURE, -6)
# vid.set(cv2.CAP_PROP_BRIGHTNESS, 0.4)
# vid.set(cv2.CAP_PROP_CONTRAST, 0.7)

prev_frame_time = 0
new_frame_time = 0

# =============== MAIN LOOP ===============
while True:
    ret, frame = vid.read()
    if not ret:
        continue

    # Detect biển số
    plates = yolo_LP_detect(frame, size=DET_SIZE)
    list_plates = plates.pandas().xyxy[0].values.tolist()
    list_read_plates = set()

    for plate in list_plates:
        x1, y1, x2, y2 = map(int, plate[:4])
        w = x2 - x1
        h = y2 - y1
        crop_img = frame[y1:y1+h, x1:x1+w]

        # Vẽ bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), color=(0, 0, 225), thickness=2)

        # Tăng chất lượng crop trước OCR
        crop_img = pad_and_resize(crop_img, out_h=256, pad_ratio=0.10)

        # Thử deskew 2x2 như cũ, nhưng kèm nhiều biến thể preprocess
        found = False
        for cc in range(0, 2):
            for ct in range(0, 2):
                deskewed = utils_rotate.deskew(crop_img, cc, ct)
                for variant in preprocess_variants(deskewed):
                    lp = helper.read_plate(yolo_license_plate, variant)
                    if lp != "unknown":
                        list_read_plates.add(lp)
                        cv2.putText(
                            frame, lp, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36, 255, 12), 2
                        )
                        found = True
                        break
                if found:
                    break
            if found:
                break

    # FPS overlay
    if SHOW_FPS:
        new_frame_time = time.time()
        fps = 0 if prev_frame_time == 0 else 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time
        cv2.putText(
            frame, f"{int(fps)}",
            (7, 70), cv2.FONT_HERSHEY_SIMPLEX, 3, (100, 255, 0), 3, cv2.LINE_AA
        )

    cv2.imshow('frame', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

vid.release()
cv2.destroyAllWindows()
