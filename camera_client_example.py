import cv2
import requests
import base64
import json
import time

# Địa chỉ Django server
DJANGO_SERVER = "http://192.168.1.184:8000"

def send_frame(frame, camera_id=1):
    """Gửi frame từ camera đến Django server"""
    try:
        # Chuyển frame sang định dạng JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        # Chuyển sang base64 để gửi qua JSON
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Chuẩn bị dữ liệu để gửi
        data = {
            "camera_id": camera_id,
            "frame": frame_base64
        }
        
        # Gửi frame đến Django server
        response = requests.post(
            f"{DJANGO_SERVER}/stream/upload/",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("Frame sent successfully")
        else:
            print(f"Error sending frame: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    # Khởi tạo camera
    cap = cv2.VideoCapture(0)  # Sử dụng camera mặc định (hoặc thay đổi số 0 để dùng camera khác)
    
    try:
        while True:
            # Đọc frame từ camera
            ret, frame = cap.read()
            if not ret:
                print("Error capturing frame")
                break
                
            # Gửi frame đến Django server
            send_frame(frame)
            
            # Đợi một chút để tránh gửi quá nhiều request
            time.sleep(0.1)  # Gửi khoảng 10 frames/giây
            
    except KeyboardInterrupt:
        print("Stopping camera stream...")
    finally:
        cap.release()

if __name__ == "__main__":
    main()