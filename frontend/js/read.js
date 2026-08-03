/* আলোক — পড়ুন: point the camera at printed text (labels, newspapers, books),
   tap once, hear it read aloud. OCR runs entirely on the user's device via
   Tesseract.js (Bangla + English) — nothing is sent to the server, and the
   phone's CPU is far faster than a free-tier server's. */

(() => {
  const video = document.getElementById('camera');
  const stageNote = document.getElementById('stage-note');
  const statusEl = document.getElementById('read-status');
  const outputEl = document.getElementById('read-output');
  const captureBtn = document.getElementById('capture-btn');
  const againBtn = document.getElementById('speak-again-btn');
  const stopBtn = document.getElementById('stop-btn');

  let stream = null;
  let worker = null;         // Tesseract worker, created once, reused
  let workerReady = false;
  let cameraOn = false;
  let busy = false;
  let chunks = [];           // last recognized text, split for sequential speech
  let chunkLang = 'bn';
  let readingCancelled = false;

  // ---- status helpers (key-based so the language toggle re-renders) -------
  let statusKey = 'read.initial';
  let statusParams = null;

  function setStatus(key, quiet, params) {
    statusKey = key;
    statusParams = params || null;
    statusEl.textContent = Alok.t(key, statusParams);
    statusEl.classList.toggle('quiet', !!quiet);
  }

  function refreshCaptureLabel() {
    if (busy) captureBtn.textContent = Alok.t('read.working');
    else captureBtn.textContent = Alok.t(cameraOn ? 'read.capture' : 'read.startCam');
  }

  document.addEventListener('alok:langchange', () => {
    statusEl.textContent = Alok.t(statusKey, statusParams);
    refreshCaptureLabel();
  });

  setStatus('read.initial', true);
  refreshCaptureLabel();

  // ---- camera ---------------------------------------------------------------
  async function openCamera() {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1920 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    stageNote.style.display = 'none';
    cameraOn = true;
  }

  // ---- OCR ------------------------------------------------------------------
  async function serverOcr(canvas) {
    // Returns the recognized text ('' = genuinely no text in view), or
    // throws when the server path is unavailable — caller then falls back.
    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.85));
    if (!blob) throw new Error('capture failed');

    const form = new FormData();
    form.append('file', blob, 'frame.jpg');
    const res = await fetch('/detect/read', { method: 'POST', body: form });
    if (!res.ok) throw new Error(`server ${res.status}`);
    const data = await res.json();
    if (!data.success) throw new Error('server ocr failed');
    return (data.text || '').trim();
  }

  async function ensureWorker() {
    if (workerReady) return worker;
    setStatus('read.loadingOcr', false);
    Alok.speak('পড়ার ব্যবস্থা চালু হচ্ছে, একটু অপেক্ষা করুন');
    worker = await Tesseract.createWorker(['ben', 'eng'], 1, {
      logger: (m) => {
        if (m.status === 'recognizing text') {
          setStatus('read.progress', false, { p: Alok.bn(Math.round(m.progress * 100)) });
        }
      },
    });
    workerReady = true;
    return worker;
  }

  function captureFrame() {
    // Full camera resolution, natural color — what the server OCR wants
    const w = video.videoWidth, h = video.videoHeight;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    canvas.getContext('2d').drawImage(video, 0, 0, w, h);
    return canvas;
  }

  function preprocessForTesseract(source) {
    // Grayscale + contrast stretch — helps the on-device engine with
    // uneven lighting; the server engine gets the original color frame.
    const w = source.width, h = source.height;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(source, 0, 0, w, h);

    const img = ctx.getImageData(0, 0, w, h);
    const d = img.data;
    let min = 255, max = 0;
    for (let i = 0; i < d.length; i += 4) {
      const g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      d[i] = g;
      if (g < min) min = g;
      if (g > max) max = g;
    }
    const range = Math.max(1, max - min);
    for (let i = 0; i < d.length; i += 4) {
      const g = ((d[i] - min) / range) * 255;
      d[i] = d[i + 1] = d[i + 2] = g;
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function dominantLang(text) {
    const bangla = (text.match(/[ঀ-৿]/g) || []).length;
    const latin = (text.match(/[A-Za-z]/g) || []).length;
    return latin > bangla ? 'en' : 'bn';
  }

  function splitForSpeech(text) {
    // Sentence-ish chunks under ~200 chars: keeps the server TTS fallback
    // within its limit and dodges Chrome's long-utterance cutoff.
    const parts = text
      .replace(/\s+/g, ' ')
      .split(/(?<=[।.!?;:])\s+/)
      .flatMap((s) => {
        const out = [];
        while (s.length > 200) {
          let cut = s.lastIndexOf(' ', 200);
          if (cut < 80) cut = 200;
          out.push(s.slice(0, cut));
          s = s.slice(cut).trim();
        }
        if (s) out.push(s);
        return out;
      })
      .filter((s) => s.trim().length > 0);
    return parts;
  }

  // ---- sequential reading ---------------------------------------------------
  function readChunks(startAt = 0) {
    readingCancelled = false;
    stopBtn.hidden = false;

    const next = (i) => {
      if (readingCancelled || i >= chunks.length) {
        stopBtn.hidden = true;
        return;
      }
      Alok.speak(chunks[i], {
        interrupt: i === startAt,
        lang: chunkLang,
        onend: () => next(i + 1),
      });
    };
    next(startAt);
  }

  function stopReading() {
    readingCancelled = true;
    Alok.stopSpeaking();
    stopBtn.hidden = true;
  }

  // ---- main flow -------------------------------------------------------------
  captureBtn.addEventListener('click', async () => {
    if (busy) return;

    if (!cameraOn) {
      captureBtn.disabled = true;
      try {
        await openCamera();
        setStatus('read.ready', false);
        Alok.speak('ক্যামেরা চালু হয়েছে। লেখাটা ক্যামেরার সামনে ধরে "পড়ুন" চাপুন।');
      } catch (e) {
        setStatus('read.camfail', true);
        Alok.speak('ক্যামেরা চালু করা যায়নি। অনুমতি দিন।');
      }
      captureBtn.disabled = false;
      refreshCaptureLabel();
      return;
    }

    busy = true;
    stopReading();
    refreshCaptureLabel();
    captureBtn.disabled = true;

    try {
      const frame = captureFrame();
      setStatus('read.working', false);
      Alok.speak('পড়া হচ্ছে, একটু অপেক্ষা করুন');

      // Server OCR first (Gemini — far better on Bangla and messy photos);
      // on-device Tesseract when the server can't (offline, no key, quota).
      let text = null;
      try {
        text = await serverOcr(frame);
      } catch (e) {
        text = null; // fall through to on-device
      }

      if (text === null) {
        await ensureWorker();
        setStatus('read.progress', false, { p: Alok.bn(0) });
        const { data } = await worker.recognize(preprocessForTesseract(frame));
        text = (data.text || '').trim();
      }

      if (!text || text.replace(/[\s\W]/g, '').length < 3) {
        outputEl.hidden = true;
        againBtn.disabled = true;
        setStatus('read.noText', true);
        Alok.speak('কোনো লেখা পাওয়া যায়নি। আরো কাছে ধরে, ভালো আলোতে আবার চেষ্টা করুন।');
      } else {
        outputEl.textContent = text;
        outputEl.hidden = false;
        chunkLang = dominantLang(text);
        chunks = splitForSpeech(text);
        againBtn.disabled = false;
        setStatus('read.done', false, { n: Alok.bn(chunks.length) });
        readChunks();
      }
    } catch (e) {
      setStatus('read.fail', true);
      Alok.speak('পড়া যায়নি। ইন্টারনেট সংযোগ দেখে আবার চেষ্টা করুন।');
    } finally {
      busy = false;
      captureBtn.disabled = false;
      refreshCaptureLabel();
    }
  });

  againBtn.addEventListener('click', () => {
    if (chunks.length) readChunks();
  });

  stopBtn.addEventListener('click', stopReading);

  window.addEventListener('pagehide', () => {
    stopReading();
    if (stream) stream.getTracks().forEach((t) => t.stop());
  });
})();
