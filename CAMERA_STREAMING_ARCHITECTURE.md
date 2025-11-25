# 🎥 Camera Streaming System Architecture

## 📋 Tổng quan

Hệ thống streaming camera từ Raspberry Pi đến browser qua Django server.

---

## 🏗️ Kiến trúc tổng thể

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Raspberry Pi   │         │  Django Server  │         │    Browser      │
│                 │         │                 │         │                 │
│  ┌───────────┐  │         │  ┌───────────┐  │         │  ┌───────────┐  │
│  │  Camera   │  │         │  │   Views   │  │         │  │   <img>   │  │
│  │           │  │         │  │           │  │         │  │  element  │  │
│  └─────┬─────┘  │         │  └─────┬─────┘  │         │  └─────▲─────┘  │
│        │        │         │        │        │         │        │        │
│  ┌─────▼─────┐  │         │  ┌─────▼─────┐  │         │        │        │
│  │  Capture  │  │         │  │File System│  │         │        │        │
│  │  & POST   │  │         │  │  (media/) │  │         │        │        │
│  └───────────┘  │         │  └───────────┘  │         │        │        │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         │    POST /api/stream       │                           │
         ├──────────────────────────►│                           │
         │    (Binary JPEG)          │                           │
         │                           │    GET /video_feed        │
         │                           │◄──────────────────────────┤
         │                           │                           │
         │                           │    MJPEG Stream           │
         │                           ├──────────────────────────►│
         │                           │    (multipart frames)     │
         │    POST /api/stream       │                           │
         ├──────────────────────────►│                           │
         │                           │                           │
         │                           │    MJPEG Stream           │
         │                           ├──────────────────────────►│
```

---

## 🔄 Data Flow (Luồng dữ liệu)

### 1️⃣ Raspberry Pi → Django (Upload Frame)

```python
# Raspberry Pi code (pseudo)
while True:
    frame = camera.capture()  # Capture JPEG
    requests.post(
        'http://server:8000/api/stream/raspberrypi_cam',
        data=frame  # Binary JPEG
    )
    time.sleep(0.033)  # ~30 FPS
```

**Django endpoint:** `/api/stream/<camera_id>`

```python
# views.py - receive_stream()
@csrf_exempt
def receive_stream(request, src):
    # 1. Nhận binary JPEG từ request.body
    # 2. Lưu vào media/streams/{src}.tmp (atomic)
    # 3. Move sang media/streams/{src}.jpg
    # 4. Return "OK"
```

**File structure:**
```
media/
  streams/
    raspberrypi_cam.jpg  ← Frame mới nhất (30 FPS)
```

---

### 2️⃣ Browser → Django (Request Stream)

```html
<!-- dashboard_user.html -->
<img src="/video_feed/raspberrypi_cam" id="camera-stream">
```

**Django endpoint:** `/video_feed/<camera_id>`

```python
# views.py - video_feed()
@login_required
def video_feed(request, src):
    # 1. Tạo StreamingHttpResponse
    # 2. Gọi gen_frames(src) generator
    # 3. Return MJPEG stream
```

---

### 3️⃣ Django Generator (Infinite Loop)

```python
# views.py - gen_frames()
def gen_frames(camera_id):
    last_frame = None
    
    while True:  # ♾️ Infinite loop
        # 1. Đọc frame từ file (get_stream_frame)
        frame = get_stream_frame(camera_id)
        
        if frame is not None:
            last_frame = frame
            # 2. Yield MJPEG frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + frame + b'\r\n')
        elif last_frame:
            # 3. Yield frame cũ nếu không có frame mới
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + last_frame + b'\r\n')
        
        time.sleep(0.033)  # 30 FPS
```

---

## 🔧 Components (Thành phần)

### 1. `receive_stream(request, src)` - Upload Endpoint

**Mục đích:** Nhận frame từ Raspberry Pi

**Flow:**
```
POST /api/stream/raspberrypi_cam
Body: <binary JPEG data>

↓

1. Tạo thư mục media/streams/
2. Ghi frame vào .tmp file
3. Move atomic sang .jpg
4. Return "OK"
```

**Atomic Write:**
- ✅ Ghi vào file `.tmp` trước
- ✅ Move sang file chính
- ✅ Tránh race condition (đọc file đang ghi)

---

### 2. `video_feed(request, src)` - Stream Endpoint

**Mục đích:** Cung cấp MJPEG stream cho browser

**Flow:**
```
GET /video_feed/raspberrypi_cam

↓

1. Create StreamingHttpResponse
2. Call gen_frames(src)
3. Set headers (no-cache, multipart)
4. Return infinite stream
```

**Headers:**
```
Content-Type: multipart/x-mixed-replace; boundary=frame
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

---

### 3. `gen_frames(camera_id)` - Generator Function

**Mục đích:** Generate MJPEG frames liên tục

**Flow:**
```
while True:
    ├─ 1. Đọc frame từ file (get_stream_frame)
    ├─ 2. Nếu có frame mới:
    │     └─ Yield frame mới
    ├─ 3. Nếu không có frame mới:
    │     └─ Yield frame cũ (QUAN TRỌNG!)
    ├─ 4. Sleep 33ms (~30 FPS)
    └─ Lặp lại
```

**Error Handling:**
- `GeneratorExit`: Client close → Exit gracefully
- `Exception`: Log error → Continue
- Max 50 errors → Stop

---

### 4. `get_stream_frame(camera_id)` - File Reader

**Mục đích:** Đọc frame mới nhất từ file

**Flow:**
```
1. Check file exists
   └─ No: Return None

2. Check file age (< 10 seconds)
   └─ Old: Return None

3. Read file with retry (3 attempts)
   ├─ Success: Return binary data
   └─ Fail: Return None
```

**Retry Logic:**
- Try 3 times
- Sleep 10ms between retries
- Handle IOError (file locked)

---

## ⚡ Performance Optimization

### Frame Rate: 30 FPS
```python
time.sleep(0.033)  # 1/30 = 0.033 seconds
```

### Cache Frame
```python
last_frame = None  # Cache frame cuối cùng

if frame is not None:
    last_frame = frame  # Update cache
    yield frame
elif last_frame:
    yield last_frame  # Reuse old frame
```

**Lợi ích:**
- ✅ Giữ connection alive (không timeout)
- ✅ Smooth playback (không bị flicker)
- ✅ Handle temporary frame loss

---

### Logging Strategy
```python
# Log mỗi 30 lần đọc (1 giây)
if counter % 30 == 0:
    print(f"📹 Reading frame: age={age}s, size={size}KB")
```

**Tránh spam logs** nhưng vẫn monitor được

---

## 🛡️ Error Handling

### File Not Found
```python
if not os.path.exists(frame_path):
    print("❌ Stream file NOT FOUND")
    return None
```

### File Too Old
```python
if file_age > 10:
    print("⚠️ Stream file too old")
    return None
```

### File Locked (Race Condition)
```python
for attempt in range(3):
    try:
        with open(frame_path, 'rb') as f:
            return f.read()
    except IOError:
        time.sleep(0.01)  # Retry
```

### Too Many Errors
```python
error_count += 1
if error_count > 50:
    print("❌ Too many errors, stopping")
    break
```

---

## 🌐 Browser Integration

### HTML
```html
<img src="{% url 'video_feed' src='raspberrypi_cam' %}" 
     id="camera-stream"
     alt="Camera stream">
```

### Auto-Reconnect (JavaScript)
```javascript
const streamImg = document.getElementById('camera-stream');

// On error → reconnect
streamImg.addEventListener('error', function() {
    setTimeout(() => {
        streamImg.src = streamImg.src.split('?')[0] + '?t=' + Date.now();
    }, 2000);
});

// Monitor health (check every 5s)
setInterval(() => {
    if (timeSinceLastLoad > 15000) {
        reconnectStream();
    }
}, 5000);
```

---

## 📊 Timeline Example

```
Time    Raspberry Pi          Django Server               Browser
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0.00s   Capture frame #1
        POST frame #1    ──►  Save to disk
                              Read frame #1          ──►  Display #1
0.03s   Capture frame #2
        POST frame #2    ──►  Save to disk
                              Read frame #2          ──►  Display #2
0.06s   Capture frame #3
        POST frame #3    ──►  Save to disk
                              Read frame #3          ──►  Display #3
...     (Continues ~30 FPS)
```

---

## 🔍 Debugging Tips

### 1. Check if Raspberry Pi is POSTing
```bash
# Monitor Django console
python manage.py runserver

# Should see:
# "POST /api/stream/raspberrypi_cam HTTP/1.1" 200
```

### 2. Check file is being updated
```bash
# PowerShell
Get-Item media\streams\raspberrypi_cam.jpg | 
    Select-Object Name, Length, LastWriteTime
```

### 3. Check stream endpoint
```bash
# Browser console (F12)
# Should see:
# ✅ Camera stream connected
```

### 4. Monitor Django logs
```
🎬 Starting stream generator for: raspberrypi_cam
📹 Reading frame for raspberrypi_cam: age=0.3s, size=34.4KB
```

---

## ⚠️ Common Issues

### Issue 1: Stream ngắt sau vài giây
**Nguyên nhân:** Generator không yield khi không có frame
**Fix:** Yield frame cũ (last_frame) để giữ connection

### Issue 2: File too old warning
**Nguyên nhân:** Raspberry Pi ngừng POST
**Fix:** Check network, restart Raspberry Pi script

### Issue 3: Empty frame file
**Nguyên nhân:** Race condition (đọc khi đang ghi)
**Fix:** Atomic write (tmp file + move)

### Issue 4: Browser timeout
**Nguyên nhân:** Generator bị exception và exit
**Fix:** Try-except + continue (không break)

---

## 🚀 Future Improvements

1. **WebSocket streaming** (instead of MJPEG)
   - Lower latency
   - Better error handling
   - Two-way communication

2. **Redis caching**
   - Store frames in Redis instead of disk
   - Faster read/write
   - Better concurrency

3. **Multiple camera support**
   - Already supports multiple cameras (via camera_id)
   - Just POST to different URLs

4. **Recording feature**
   - Save frames to video file
   - On-demand recording

5. **Motion detection**
   - Only stream when motion detected
   - Save bandwidth

---

## 📚 References

- [MJPEG Format](https://en.wikipedia.org/wiki/Motion_JPEG)
- [Django StreamingHttpResponse](https://docs.djangoproject.com/en/stable/ref/request-response/#streaminghttpresponse-objects)
- [Python Generators](https://docs.python.org/3/howto/functional.html#generators)

---

**Last Updated:** November 25, 2025
**Version:** 2.0
**Author:** Smart Parking Team
