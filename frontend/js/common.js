/* আলোক — shared helpers: Bangla speech, settings, numerals */

window.Alok = (() => {

  // ---- Settings (persisted) ------------------------------------------------
  const DEFAULTS = {
    speechRate: 1.0,     // 0.5–1.5
    confidence: 0.5,     // 0.25–0.8
    frameInterval: 700,  // ms between frames sent to the server
  };

  function getSettings() {
    try {
      return { ...DEFAULTS, ...JSON.parse(localStorage.getItem('alok-settings') || '{}') };
    } catch {
      return { ...DEFAULTS };
    }
  }

  function saveSettings(patch) {
    const merged = { ...getSettings(), ...patch };
    localStorage.setItem('alok-settings', JSON.stringify(merged));
    return merged;
  }

  // ---- Bangla speech -------------------------------------------------------
  // Prefer the device's own Bangla voice (instant, offline — Android phones
  // have one). If there is none (typical on desktop PCs), fall back to the
  // server's /detect/tts endpoint, which returns cached gTTS audio.
  let bnVoice = null;
  let fallbackAudio = null;
  let speakingNow = false;
  let pendingText = null; // one slot: the newest waiting announcement wins

  function pickVoice() {
    const voices = speechSynthesis.getVoices();
    bnVoice =
      voices.find(v => v.lang && v.lang.toLowerCase().startsWith('bn')) || null;
    return bnVoice;
  }

  if ('speechSynthesis' in window) {
    pickVoice();
    speechSynthesis.onvoiceschanged = pickVoice;
  }

  function advance() {
    speakingNow = false;
    fallbackAudio = null;
    if (pendingText) {
      const next = pendingText;
      pendingText = null;
      speakNow(next);
    }
  }

  function speakNow(text) {
    speakingNow = true;

    // Voices load asynchronously — re-check at speak time
    if ('speechSynthesis' in window && (bnVoice || pickVoice())) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'bn-BD';
      u.voice = bnVoice;
      u.rate = getSettings().speechRate;
      u.onend = advance;
      u.onerror = advance;
      speechSynthesis.speak(u);
      return;
    }

    // No local Bangla voice: play server-synthesized audio
    fallbackAudio = new Audio('/detect/tts?text=' + encodeURIComponent(text));
    fallbackAudio.playbackRate = getSettings().speechRate;
    fallbackAudio.onended = advance;
    fallbackAudio.onerror = advance;
    fallbackAudio.play().catch(advance);
  }

  /**
   * Speak Bangla text. The current sentence always finishes; if new text
   * arrives while speaking, it waits its turn (and newer text replaces it —
   * only the latest scene is worth hearing). Pass interrupt=true to cut
   * off the current sentence immediately.
   */
  function speak(text, { interrupt = false } = {}) {
    if (!text) return;
    if (interrupt) {
      stopSpeaking();
      speakNow(text);
      return;
    }
    if (speakingNow) {
      pendingText = text;
      return;
    }
    speakNow(text);
  }

  function stopSpeaking() {
    // Clear state first so the cancel/pause callbacks don't re-speak
    pendingText = null;
    speakingNow = false;
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    if (fallbackAudio) {
      fallbackAudio.onended = null;
      fallbackAudio.onerror = null;
      fallbackAudio.pause();
      fallbackAudio = null;
    }
  }

  // ---- Numerals (Bengali digits in bn mode, western in en mode) -------------
  const BN_DIGITS = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];

  function uiLang() {
    return localStorage.getItem('alok-lang') === 'en' ? 'en' : 'bn';
  }

  function bn(number) {
    if (uiLang() === 'en') return String(number);
    return String(number).replace(/\d/g, d => BN_DIGITS[d]);
  }

  // Bangla word for a taka denomination, e.g. "100 Taka" -> "একশো টাকা"
  const TAKA_WORDS = {
    1: 'এক', 2: 'দুই', 5: 'পাঁচ', 10: 'দশ', 20: 'বিশ',
    50: 'পঞ্চাশ', 100: 'একশো', 200: 'দুইশো', 500: 'পাঁচশো', 1000: 'এক হাজার',
  };

  function takaValue(className) {
    const m = /^(\d+)\s*Taka$/i.exec(className || '');
    return m ? parseInt(m[1], 10) : null;
  }

  // Display label follows the UI language; speech always uses the Bangla one
  function takaLabelBn(value) {
    return `${TAKA_WORDS[value] || String(value)} টাকার নোট`;
  }

  function takaLabel(value) {
    if (uiLang() === 'en') return `${value} taka note`;
    return takaLabelBn(value);
  }

  // ---- Haptics -------------------------------------------------------------
  function buzz(ms = 80) {
    if (navigator.vibrate) navigator.vibrate(ms);
  }

  // ---- Service worker ------------------------------------------------------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  return { getSettings, saveSettings, speak, stopSpeaking, bn, takaValue, takaLabel, takaLabelBn, buzz };
})();
