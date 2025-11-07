#!/usr/bin/env python3
import cv2
import requests
import time
import numpy as np
from datetime import datetime
import threading
import pytesseract
from PIL import Image
import io
import socket
import netifaces
import concurrent.futures

def get_network_interfaces():
    """Lấy danh sách các interface mạng"""
    interfaces = []
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                if 'addr' in addr and addr['addr'] != '127.0.0.1':
                    interfaces.append((iface, addr['addr'], addr['netmask']))
    return interfaces

def get_network_range(ip, netmask):
    """Tính toán dải địa chỉ IP của mạng"""
    import ipaddress
    network = ipaddress.IPv4Network(f'{ip}/{netmask}', strict=False)
    return network

def find_django_server(port=8000, timeout=0.1):
    """Tự động tìm Django server trên mạng LAN"""
    print("🔍 Đang tìm Django server...")
CAMERA_ID = 0  # ID của camera (thường là 0 cho camera đầu tiên)
STREAM_INTERVAL = 0.1  # 100ms giữa các frame
DETECT_INTERVAL = 2.0  # 2 giây giữa các lần nhận diện

class ParkingCamera:
    def __init__(self):
        self.camera = cv2.VideoCapture(CAMERA_ID)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.last_detect_time = 0
        self.running = True

    def detect_license_plate(self, image):
        """Nhận diện biển số xe từ ảnh"""
        try:
            # Chuyển ảnh sang grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Làm mịn ảnh để giảm nhiễu
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Phát hiện cạnh
            edges = cv2.Canny(blur, 50, 150)
            
            # Tìm contours
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Lọc các contour có hình dạng giống biển số
            possible_plates = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 1000:  # Lọc bỏ các contour quá nhỏ
                    x, y, w, h = cv2.boundingRect(cnt)
                    ratio = w/h
                    if 2.0 <= ratio <= 5.0:  # Tỷ lệ thường thấy của biển số xe
                        plate_img = gray[y:y+h, x:x+w]
                        possible_plates.append(plate_img)

            # Nhận dạng text từ các vùng có thể là biển số
            for plate in possible_plates:
                # Tiền xử lý ảnh để cải thiện OCR
                plate = cv2.resize(plate, None, fx=2, fy=2)
                _, plate = cv2.threshold(plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # OCR
                text = pytesseract.image_to_string(plate, config='--psm 7')
                text = ''.join(c for c in text if c.isalnum())
                
                if len(text) >= 7:  # Biển số thường có ít nhất 7 ký tự
                    return text, 0.85  # Confidence score giả định
            
            return None, 0

        except Exception as e:
            print(f"Error in license plate detection: {e}")
            return None, 0

    def send_frame(self, frame):
        """Gửi frame đến Django server"""
        try:
            # Chuyển frame sang JPEG
            _, jpeg = cv2.imencode('.jpg', frame)
            
            # Gửi frame tới endpoint stream
            response = requests.post(
                f"{DJANGO_SERVER}/stream/raspberrypi_cam/",
                data=jpeg.tobytes(),
                headers={'Content-Type': 'image/jpeg'}
            )
            
            if response.status_code != 200:
                print(f"Error sending frame: {response.status_code}")
                
        except Exception as e:
            print(f"Error streaming frame: {e}")

    def send_detection(self, frame, plate_number, confidence):
        """Gửi kết quả nhận diện đến Django server"""
        try:
            # Chuyển frame sang JPEG
            _, jpeg = cv2.imencode('.jpg', frame)
            
            # Chuẩn bị dữ liệu
            files = {
                'image': ('detection.jpg', jpeg.tobytes(), 'image/jpeg')
            }
            data = {
                'plate': plate_number,
                'confidence': str(confidence),
                'source': 'raspberrypi_cam'
            }
            
            # Gửi kết quả nhận diện
            response = requests.post(
                f"{DJANGO_SERVER}/upload_detection/",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                print(f"Detection sent: {plate_number} ({confidence})")
            else:
                print(f"Error sending detection: {response.status_code}")
                
        except Exception as e:
            print(f"Error sending detection: {e}")

    def run(self):
        """Chạy camera và xử lý frame"""
        print("Starting camera...")
        
        while self.running:
            try:
                ret, frame = self.camera.read()
                if not ret:
                    print("Error capturing frame")
                    time.sleep(1)
                    continue

                # Gửi frame để stream
                self.send_frame(frame)

                # Kiểm tra xem đã đến lúc nhận diện chưa
                current_time = time.time()
                if current_time - self.last_detect_time >= DETECT_INTERVAL:
                    # Nhận diện biển số
                    plate_number, confidence = self.detect_license_plate(frame)
                    
                    if plate_number:
                        # Gửi kết quả nhận diện
                        self.send_detection(frame, plate_number, confidence)
                    
                    self.last_detect_time = current_time

                time.sleep(STREAM_INTERVAL)

            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(1)

        self.camera.release()

    def stop(self):
        """Dừng camera"""
        self.running = False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", help="Django server URL", default="http://localhost:8000")
    args = parser.parse_args()
    
    DJANGO_SERVER = args.server
    
    try:
        camera = ParkingCamera()
        print(f"Connected to server: {DJANGO_SERVER}")
        camera.run()
    except KeyboardInterrupt:
        print("\nStopping camera...")
        camera.stop()