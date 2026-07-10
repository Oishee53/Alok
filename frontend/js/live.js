/* আলোক — live detection: phone camera → WebSocket → spoken Bangla */

(() => {
  const video = document.getElementById('camera');
  const overlay = document.getElementById('overlay');
  const stageNote = document.getElementById('stage-note');
  const announcementEl = document.getElementById('announcement');
  const connDot = document.getElementById('conn-dot');
  const connLabel = document.getElementById('conn-label');
  const fpsStatus = document.getElementById('fps-status');
  const toggleBtn = document.getElementById('toggle-btn');
  const repeatBtn = document.getElementById('repeat-btn');

  // Frames are downscaled before sending: enough for detection, light on data.
  // 640 matches YOLO's native input size — smaller loses banknote detail.
  const SEND_WIDTH = 640;

  // A changed scene is only spoken after it stays the same for this many
  // consecutive results (kills flicker when an object hovers on a direction
  // boundary), and never sooner than this many ms after the last sentence.
  const STABLE_RESULTS_NEEDED = 2;
  const MIN_ANNOUNCE_GAP = 2500;
  const RESPEAK_AFTER = 8000;

  let running = false;
  let ws = null;
  let stream = null;
  let wakeLock = null;
  let lastSpoken = '';
  let lastSpokenAt = 0;
  let lastSentAt = 0;
  let sentW = 0, sentH = 0;
  let candidateText = '';
  let candidateCount = 0;
  let reconnectAttempts = 0;
  const captureCanvas = document.createElement('canvas');

  // ---- Settings UI ----------------------------------------------------------
  const rateInput = document.getElementById('rate');
  const confInput = document.getElementById('conf');
  const intervalInput = document.getElementById('interval');

  function refreshSettingsUI() {
    const s = Alok.getSettings();
    rateInput.value = s.speechRate;
    confInput.value = s.confidence;
    intervalInput.value = s.frameInterval;
    document.getElementById('rate-value').textContent = Alok.bn(s.speechRate.toFixed(1));
    document.getElementById('conf-value').textContent = Alok.bn(Math.round(s.confidence * 100)) + '%';
    document.getElementById('interval-value').textContent =
      Alok.t('live.intervalUnit', { s: Alok.bn((s.frameInterval / 1000).toFixed(1)) });
  }

  rateInput.addEventListener('input', () => {
    Alok.saveSettings({ speechRate: parseFloat(rateInput.value) });
    refreshSettingsUI();
  });
  confInput.addEventListener('input', () => {
    Alok.saveSettings({ confidence: parseFloat(confInput.value) });
    refreshSettingsUI();
    // Confidence rides on the WS URL, so a change needs a fresh connection
    if (running) { closeSocket(); openSocket(); }
  });
  intervalInput.addEventListener('input', () => {
    Alok.saveSettings({ frameInterval: parseInt(intervalInput.value, 10) });
    refreshSettingsUI();
  });

  refreshSettingsUI();

  // ---- Status helpers -------------------------------------------------------
  // Dynamic texts remember their i18n key so a language switch re-renders them
  let connKey = 'conn.none';
  let announcementKey = 'live.initial'; // null while showing a real detection

  function setConn(state, key) {
    connKey = key;
    connDot.className = 'status-dot' + (state === 'on' ? ' on' : state === 'err' ? ' err' : '');
    connLabel.textContent = Alok.t(key);
  }

  function setAnnouncement(textOrKey, { quiet = false, isKey = false } = {}) {
    announcementKey = isKey ? textOrKey : null;
    announcementEl.textContent = isKey ? Alok.t(textOrKey) : textOrKey;
    announcementEl.classList.toggle('quiet', quiet);
  }

  function refreshToggleLabel() {
    toggleBtn.textContent = Alok.t(running ? 'live.stop' : 'live.start');
  }

  document.addEventListener('alok:langchange', () => {
    refreshSettingsUI();
    connLabel.textContent = Alok.t(connKey);
    if (announcementKey) announcementEl.textContent = Alok.t(announcementKey);
    refreshToggleLabel();
  });

  // ---- Camera ----------------------------------------------------------------
  async function openCamera() {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    stageNote.style.display = 'none';
    try {
      wakeLock = await navigator.wakeLock.request('screen');
    } catch { /* not supported — fine */ }
  }

  function closeCamera() {
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    video.srcObject = null;
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
    stageNote.style.display = '';
    overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height);
  }

  // ---- WebSocket --------------------------------------------------------------
  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const conf = Alok.getSettings().confidence;
    return `${proto}://${location.host}/detect/ws?confidence=${conf}`;
  }

  function openSocket() {
    setConn('', 'conn.connecting');
    ws = new WebSocket(wsUrl());
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setConn('on', 'conn.connected');
      reconnectAttempts = 0;
      sendFrame(); // kick off the send→receive loop
    };

    ws.onmessage = (event) => {
      let payload;
      try { payload = JSON.parse(event.data); } catch { payload = null; }
      if (payload) handleResult(payload);
      scheduleNextFrame();
    };

    ws.onclose = () => {
      if (running) {
        reconnectAttempts += 1;
        setConn('err', 'conn.lost');
        // After a few silent retries, say so loudly — a frozen announcement
        // box with only a small status-line change reads as "the app thinks
        // the camera is off" even though it's actively retrying underneath.
        if (reconnectAttempts === 3) {
          setAnnouncement('conn.trouble', { quiet: true, isKey: true });
          Alok.speak('সার্ভারের সাথে সংযোগ হচ্ছে না। চেষ্টা চলছে।', { interrupt: true });
        }
        setTimeout(() => { if (running) openSocket(); }, 1500);
      } else {
        setConn('', 'conn.none');
      }
    };

    ws.onerror = () => { try { ws.close(); } catch { } };
  }

  function closeSocket() {
    if (ws) {
      ws.onclose = null;
      try { ws.close(); } catch { }
      ws = null;
    }
  }

  // ---- Frame loop: send one, wait for the answer, send the next ---------------
  function sendFrame() {
    if (!running || !ws || ws.readyState !== WebSocket.OPEN || video.videoWidth === 0) return;

    sentW = SEND_WIDTH;
    sentH = Math.round(SEND_WIDTH * video.videoHeight / video.videoWidth);
    captureCanvas.width = sentW;
    captureCanvas.height = sentH;
    captureCanvas.getContext('2d').drawImage(video, 0, 0, sentW, sentH);

    captureCanvas.toBlob(async (blob) => {
      if (!blob || !running || !ws || ws.readyState !== WebSocket.OPEN) return;
      lastSentAt = performance.now();
      ws.send(await blob.arrayBuffer());
    }, 'image/jpeg', 0.8);
  }

  function scheduleNextFrame() {
    if (!running) return;
    const interval = Alok.getSettings().frameInterval;
    const elapsed = performance.now() - lastSentAt;
    setTimeout(sendFrame, Math.max(0, interval - elapsed));
  }

  // ---- Results -----------------------------------------------------------------
  function handleResult(payload) {
    const ms = Math.round(performance.now() - lastSentAt);
    fpsStatus.textContent = `${Alok.bn(ms)} ${Alok.t('unit.ms')}`;

    if (!payload.success) return;

    drawBoxes(payload.detections || []);

    const text = payload.announcement || '';
    const hasObjects = (payload.total_objects || 0) > 0;

    if (hasObjects) {
      setAnnouncement(text);

      // Count how long this exact announcement has been stable
      if (text === candidateText) {
        candidateCount += 1;
      } else {
        candidateText = text;
        candidateCount = 1;
      }

      const now = performance.now();
      const changed = text !== lastSpoken;
      const stable = candidateCount >= STABLE_RESULTS_NEEDED;
      const gapOk = now - lastSpokenAt > MIN_ANNOUNCE_GAP;
      const staleEnough = now - lastSpokenAt > RESPEAK_AFTER;

      if ((changed && stable && gapOk) || staleEnough) {
        Alok.speak(text); // queues politely — never cuts a sentence short
        Alok.buzz(70);
        lastSpoken = text;
        lastSpokenAt = now;
      }
    } else {
      setAnnouncement('live.nothing', { quiet: true, isKey: true });
      candidateText = '';
      candidateCount = 0;
      if (lastSpoken !== '') {
        // Say "nothing anymore" once when objects leave the scene
        Alok.speak('এখন আর কিছু দেখছি না');
        lastSpoken = '';
        lastSpokenAt = performance.now();
      }
    }
  }

  function drawBoxes(detections) {
    overlay.width = video.videoWidth || sentW;
    overlay.height = video.videoHeight || sentH;
    const ctx = overlay.getContext('2d');
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (!sentW) return;

    const sx = overlay.width / sentW;
    const sy = overlay.height / sentH;

    ctx.lineWidth = 4;
    ctx.font = 'bold 22px "Noto Sans Bengali", sans-serif';

    for (const d of detections) {
      const [x1, y1, x2, y2] = d.bbox;
      const color = d.source_model === 'custom' ? '#ffb800' : '#8fd694';
      ctx.strokeStyle = color;
      ctx.strokeRect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy);

      const label = d.announcement_bn || d.class_name;
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(11,10,7,0.85)';
      ctx.fillRect(x1 * sx, Math.max(0, y1 * sy - 32), tw + 16, 32);
      ctx.fillStyle = color;
      ctx.fillText(label, x1 * sx + 8, Math.max(22, y1 * sy - 8));
    }
  }

  // ---- Start / stop ---------------------------------------------------------
  async function start() {
    toggleBtn.disabled = true;
    try {
      await openCamera();
    } catch (e) {
      toggleBtn.disabled = false;
      setAnnouncement('live.camfail', { quiet: true, isKey: true });
      Alok.speak('ক্যামেরা চালু করা যায়নি। অনুমতি দিন।');
      return;
    }
    running = true;
    openSocket();
    refreshToggleLabel();
    toggleBtn.classList.remove('btn-primary');
    toggleBtn.classList.add('btn-danger');
    toggleBtn.disabled = false;
    repeatBtn.disabled = false;
    Alok.speak('লাইভ দেখা শুরু হয়েছে। ফোনটা সামনে ধরুন।');
  }

  function stop() {
    running = false;
    closeSocket();
    closeCamera();
    Alok.stopSpeaking();
    setConn('', 'conn.none');
    setAnnouncement('live.stopped', { quiet: true, isKey: true });
    fpsStatus.textContent = '';
    refreshToggleLabel();
    toggleBtn.classList.add('btn-primary');
    toggleBtn.classList.remove('btn-danger');
    repeatBtn.disabled = true;
    lastSpoken = '';
    candidateText = '';
    candidateCount = 0;
    reconnectAttempts = 0;
  }

  toggleBtn.addEventListener('click', () => (running ? stop() : start()));

  repeatBtn.addEventListener('click', () => {
    const text = announcementEl.textContent.trim();
    if (text) Alok.speak(text);
  });

  // Re-acquire the wake lock when the user returns to the tab
  document.addEventListener('visibilitychange', async () => {
    if (running && document.visibilityState === 'visible' && !wakeLock) {
      try { wakeLock = await navigator.wakeLock.request('screen'); } catch { }
    }
  });

  window.addEventListener('pagehide', stop);
})();
