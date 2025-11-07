#!/usr/bin/env python3
# server.py — Flask server hiển thị ảnh & luồng camera từ Raspberry Pi

import os
import io
from datetime import datetime
from collections import deque
from pathlib import Path
from flask import Flask, request, jsonify, Response, render_template_string, send_from_directory, abort
from werkzeug.utils import secure_filename
from threading import Lock

# ================= CONFIG =================
HOST = "0.0.0.0"
PORT = 8000
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
MAX_HISTORY = 200
ALLOWED_EXT = {"jpg", "jpeg", "png"}
# ==========================================

app = Flask(__name__, static_url_path='', static_folder='.')
history = deque(maxlen=MAX_HISTORY)

# --- MJPEG streaming store ---
streams = {}
stream_locks = {}

# ================= TEMPLATE =================
HOME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>License Plate Viewer + Stream</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body { font-family: Arial, sans-serif; background: #fafafa; margin: 20px; }
    h2 { margin-top: 0; }
    .layout { display: flex; gap: 20px; }
    .left, .right { flex: 1; }
    video, img { max-width: 100%; border: 1px solid #ccc; border-radius: 6px; }
    table { border-collapse: collapse; width: 100%; margin-top: 20px; }
    th, td { border: 1px solid #ccc; padding: 6px; text-align: left; }
    th { background: #f2f2f2; }
  </style>
</head>
<body>
  <h2>🚗 License Plate Recognition & Live Stream</h2>

  <div class="layout">
    <div class="left">
      <h3>🎥 Live Stream</h3>
      <img id="stream" src="/video_feed/raspberrypi_cam" width="100%" />
    </div>

    <div class="right">
      <h3>📋 Latest Detection</h3>
      <div id="latest">
        {% if latest %}
          <div><b>{{ latest.time }}</b> — <em>{{ latest.plate }}</em> ({{ latest.conf }}) from {{ latest.src }}</div>
          <img id="latest_img" class="preview" src="/{{ latest.path }}?t={{ ts }}" alt="latest">
        {% else %}
          <div class="small">No detections yet.</div>
        {% endif %}
      </div>
    </div>
  </div>

  <h3>🕘 All Detections</h3>
  <table>
    <thead><tr><th>Time</th><th>Plate</th><th>Confidence</th><th>Source</th><th>Image</th></tr></thead>
    <tbody id="history_tbody">
      {% for p in history|reverse %}
      <tr>
        <td>{{ p.time }}</td>
        <td>{{ p.plate }}</td>
        <td>{{ p.conf }}</td>
        <td>{{ p.src }}</td>
        <td>{% if p.path %}<a href="/{{ p.path }}" target="_blank">View</a>{% else %}-{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

<script>
setInterval(()=>{
  fetch('/_latest').then(r=>r.json()).then(j=>{
    if(!j.latest) return;
    document.getElementById('latest').innerHTML =
      `<div><b>${j.latest.time}</b> — <em>${j.latest.plate}</em> (${j.latest.conf}) from ${j.latest.src}</div>
       <img src="/${j.latest.path}?t=${Date.now()}" width="100%">`;
    let rows = '';
    for(let i=j.history.length-1; i>=0; i--){
      const p=j.history[i];
      const img=p.path?`<a href="/${p.path}" target="_blank">View</a>`:'-';
      rows+=`<tr><td>${p.time}</td><td>${p.plate}</td><td>${p.conf}</td><td>${p.src}</td><td>${img}</td></tr>`;
    }
    document.getElementById('history_tbody').innerHTML=rows;
  });
},3000);
</script>
</body>
</html>
"""
# ===============================================================

@app.route('/')
def home():
    latest = history[-1] if history else None
    return render_template_string(HOME_HTML, latest=latest, history=list(history), ts=int(datetime.now().timestamp()*1000))

@app.route('/_latest')
def api_latest():
    latest = history[-1] if history else None
    return jsonify({"latest": latest, "history": list(history)})

# --- endpoint nhận frame stream từ Pi ---
@app.route('/api/stream/<src>', methods=['POST'])
def stream_upload(src):
    frame_bytes = request.data
    if not frame_bytes:
        return "empty", 400
    if src not in stream_locks:
        stream_locks[src] = Lock()
    with stream_locks[src]:
        streams[src] = frame_bytes
    return "ok", 200

# --- endpoint hiển thị stream ---
@app.route('/video_feed/<src>')
def video_feed(src):
    def gen():
        while True:
            if src in streams:
                with stream_locks[src]:
                    frame = streams[src]
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.1)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/upload/', methods=['POST'])
def upload():
    plate = request.form.get("plate", "").strip()
    confidence = request.form.get("confidence", "").strip()
    src = request.form.get("source", "").strip() or "unknown"
    image = request.files.get("image")

    saved_path = None
    if image and image.filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(f"{plate or 'unknown'}_{ts}.jpg")
        target = UPLOAD_FOLDER / filename
        image.save(str(target))
        saved_path = str(target.as_posix())

    entry = {
        "plate": plate,
        "conf": confidence,
        "src": src,
        "path": saved_path,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history.append(entry)
    print(f"📸 {plate} ({confidence}) từ {src}")
    return jsonify({"status": "ok", "plate": plate})

if __name__ == '__main__':
    print(f"🌐 Flask server running on http://{HOST}:{PORT}")
    print(f"📁 Upload folder: {UPLOAD_FOLDER.resolve()}")
    app.run(host=HOST, port=PORT, threaded=True)

