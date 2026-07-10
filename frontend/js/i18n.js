/* আলোক — bilingual UI (Bangla default, English toggle).
   Extends the Alok namespace from common.js: Alok.t(), Alok.getLang(), Alok.setLang().
   Spoken detection announcements are always Bangla — only the UI switches. */

(() => {
  const STRINGS = {
    // ---- shared chrome ----
    'skip':        { bn: 'মূল বিষয়ে যান', en: 'Skip to content' },
    'nav.home':    { bn: 'হোম', en: 'Home' },
    'nav.live':    { bn: 'লাইভ', en: 'Live' },
    'nav.help':    { bn: 'সাহায্য', en: 'Help' },
    'nav.aria':    { bn: 'প্রধান মেনু', en: 'Main menu' },
    'footer.1':    { bn: 'আলোক — দৃষ্টিপ্রতিবন্ধী মানুষের জন্য, বিনামূল্যে।', en: 'Alok — free assistive vision for blind and low-vision people.' },
    'footer.2':    { bn: 'Open source assistive vision. <a href="/docs">API docs</a>', en: 'Open source assistive vision. <a href="/docs">API docs</a>' },

    // ---- landing ----
    'title.index': { bn: 'আলোক — যা দেখা যায় না, তা শোনা যায়', en: 'Alok — what can’t be seen can be heard' },
    'hero.h1':     { bn: 'যা দেখা যায় না,<br>তা <em>শোনা</em> যায়।', en: 'What can’t be seen<br>can be <em>heard</em>.' },
    'hero.tagline': {
      bn: 'আলোক আপনার ফোনের ক্যামেরা দিয়ে টাকার নোট আর আশপাশের জিনিস চিনে পরিষ্কার বাংলায় বলে দেয় — কোন জিনিস, কোন দিকে, কত কাছে।',
      en: 'Alok uses your phone camera to recognize banknotes and everyday objects, then says what it sees out loud in Bangla — what it is, which direction, how close.',
    },
    'hero.alt': {
      bn: 'Alok speaks what your camera sees — banknotes and everyday objects, in Bangla.',
      en: 'আলোক আপনার ক্যামেরায় যা দেখে, তা বাংলায় বলে দেয়।',
    },
    'torch.main':  { bn: 'শুরু করুন', en: 'Start' },
    'torch.sub':   { bn: 'Start', en: 'শুরু করুন' },
    'act.help':    { bn: 'ব্যবহারের নিয়ম', en: 'How to use' },
    'feat.title':  { bn: 'আলোক কী কী পারে', en: 'What Alok can do' },
    'feat1.h':     { bn: 'টাকা চেনে', en: 'Recognizes taka' },
    'feat1.p': {
      bn: 'ক্যামেরার সামনে নোট ধরলেই <b>১ থেকে ১০০০ টাকার</b> যেকোনো নোট চিনে সাথে সাথে বলে দেয়।',
      en: 'Hold a note in front of the camera and it names <b>any note from ৳1 to ৳1000</b>, instantly.',
    },
    'feat2.h':     { bn: 'আশপাশ চেনে', en: 'Reads the surroundings' },
    'feat2.p': {
      bn: 'মানুষ, গাড়ি, চেয়ার, দরজাসহ <b>৮০ রকমের বেশি জিনিস</b> — শুধু কী আছে তা নয়, <b>কোন দিকে ও কত কাছে</b> তাও বলে।',
      en: 'People, cars, chairs, and <b>80+ kinds of objects</b> — not just what is there, but <b>which direction and how close</b>.',
    },
    'feat3.h':     { bn: 'বাংলায় বলে', en: 'Speaks in Bangla' },
    'feat3.p': {
      bn: 'সব ঘোষণা <b>আপনার ফোনের নিজের কণ্ঠে</b>, সাথে সাথে। অনিশ্চিত হলে "সম্ভবত" বলে সাবধান করে — ভুল ভরসা দেয় না।',
      en: 'Every announcement comes from <b>your phone’s own voice</b>, instantly. When unsure it says <i>shombhoboto</i> ("possibly") — it never fakes confidence.',
    },
    'how.title':   { bn: 'কীভাবে ব্যবহার করবেন', en: 'How to use it' },
    'how1.h':      { bn: 'শুরু করুন বোতামে চাপ দিন', en: 'Tap the Start button' },
    'how1.p':      { bn: 'ক্যামেরা চালু করার অনুমতি চাইলে "Allow" দিন — একবারই লাগবে।', en: 'When asked for camera permission, tap "Allow" — you only do this once.' },
    'how2.h':      { bn: 'ফোনটা সামনে ধরুন', en: 'Hold the phone out' },
    'how2.p':      { bn: 'টাকার নোট হলে হাতের তালুতে মেলে ধরুন। রাস্তায় হলে ফোনের ক্যামেরা সামনের দিকে রাখুন।', en: 'For banknotes, lay the note flat on your palm. Outdoors, point the camera ahead of you.' },
    'how3.h':      { bn: 'শুনুন', en: 'Listen' },
    'how3.p':      { bn: 'আলোক নিজে থেকেই বলবে: "সামনে একটি একশো টাকার নোট, খুব কাছে।"', en: 'Alok speaks on its own: "A 100 taka note ahead, very close."' },
    'install.title': { bn: 'ফোনে অ্যাপের মতো রাখুন', en: 'Keep it like an app' },
    'install.p': {
      bn: 'Chrome-এ এই পাতা খুলে মেনু (⋮) থেকে <b>"Add to Home screen"</b> চাপুন। হোম স্ক্রিনে আলোকের আইকন চলে আসবে — আলাদা করে কিছু ইনস্টল করতে হবে না।',
      en: 'Open this page in Chrome, then choose <b>"Add to Home screen"</b> from the menu (⋮). Alok’s icon appears on your home screen — nothing else to install.',
    },

    // ---- live page ----
    'title.live':  { bn: 'লাইভ দেখা — আলোক', en: 'Live — Alok' },
    'live.stagenote': { bn: '"শুরু করুন" চাপলে ক্যামেরা চালু হবে।', en: 'Tap "Start" to turn on the camera.' },
    'live.initial': { bn: 'এখনো কিছু দেখা হয়নি।', en: 'Nothing seen yet.' },
    'live.settings': { bn: 'সেটিংস', en: 'Settings' },
    'live.rate':   { bn: 'কণ্ঠের গতি', en: 'Voice speed' },
    'live.conf':   { bn: 'সংবেদনশীলতা (কম = বেশি জিনিস ধরবে)', en: 'Sensitivity (lower = detects more)' },
    'live.interval': { bn: 'কত ঘন ঘন দেখবে', en: 'How often it looks' },
    'live.intervalUnit': { bn: '{s} সেকেন্ডে একবার', en: 'every {s} s' },
    'live.start':  { bn: 'শুরু করুন', en: 'Start' },
    'live.stop':   { bn: 'থামুন', en: 'Stop' },
    'live.repeat': { bn: 'আবার বলুন', en: 'Say it again' },
    'live.stopped': { bn: 'বন্ধ আছে। আবার শুরু করতে "শুরু করুন" চাপুন।', en: 'Stopped. Tap "Start" to begin again.' },
    'live.nothing': { bn: 'আশপাশে কিছু পাওয়া যাচ্ছে না।', en: 'Nothing detected nearby.' },
    'live.camfail': { bn: 'ক্যামেরা চালু করা যায়নি। ব্রাউজারে ক্যামেরার অনুমতি দিন।', en: 'Could not open the camera. Allow camera access in the browser.' },
    'conn.none':   { bn: 'সংযোগ নেই', en: 'Not connected' },
    'conn.connecting': { bn: 'সংযোগ হচ্ছে…', en: 'Connecting…' },
    'conn.connected': { bn: 'সংযুক্ত', en: 'Connected' },
    'conn.lost':   { bn: 'সংযোগ গেছে — আবার চেষ্টা হচ্ছে…', en: 'Connection lost — retrying…' },
    'unit.ms':     { bn: 'মি.সে.', en: 'ms' },

    // ---- help page ----
    'title.help':  { bn: 'সাহায্য — আলোক', en: 'Help — Alok' },
    'help.h1':     { bn: 'ব্যবহারের নিয়ম', en: 'How to use Alok' },
    'help.intro': {
      bn: 'আলোক ফোনের ক্যামেরা দিয়ে <b>লাইভ</b> দেখে — টাকার নোট আর আশপাশের জিনিস চিনে সাথে সাথে বাংলায় বলে শোনায়।',
      en: 'Alok watches <b>live</b> through the phone camera — it recognizes banknotes and everyday objects and speaks them in Bangla as they appear.',
    },
    'help.s1.h':   { bn: 'লাইভ মোড', en: 'Live mode' },
    'help.s1.body': {
      bn: '<li><b>"শুরু করুন"</b> চাপুন — প্রথমবার ক্যামেরার অনুমতি চাইবে, "Allow" দিন।</li>\n<li>ফোনের পেছনের ক্যামেরা সামনের দিকে ধরুন। আলোক নিজে থেকেই বলতে থাকবে কী দেখছে — <b>কোন জিনিস, কোন দিকে (বামে / সামনে / ডানে), আর খুব কাছে হলে সেটাও</b>।</li>\n<li><b>টাকা চেনাতে:</b> নোটটা হাতের তালুতে মেলে ধরে ক্যামেরার সামনে আনুন — ১ থেকে ১০০০ টাকার সব নোট চেনে।</li>\n<li>কোনো ঘোষণা মিস করলে <b>"আবার বলুন"</b> চাপুন।</li>\n<li>আলোক অনিশ্চিত হলে <b>"সম্ভবত"</b> বলে — তখন আরেকটু কাছে বা ভালো আলোতে ধরুন।</li>',
      en: '<li>Tap <b>"Start"</b> — the first time, the browser asks for camera permission; tap "Allow".</li>\n<li>Point the rear camera ahead of you. Alok keeps announcing what it sees — <b>what it is, which direction (left / ahead / right), and when something is very close</b>.</li>\n<li><b>To identify money:</b> lay the note flat on your palm and bring it in front of the camera — it knows every note from ৳1 to ৳1000.</li>\n<li>Missed an announcement? Tap <b>"Say it again"</b>.</li>\n<li>When Alok is unsure it says <b>"possibly"</b> — move closer or find better light.</li>',
    },
    'help.s3.h':   { bn: 'ভালো ফল পাওয়ার কৌশল', en: 'Tips for better results' },
    'help.s3.body': {
      bn: '<li>যথেষ্ট আলো রাখুন — দিনের আলো বা ঘরের বাতি জ্বালিয়ে।</li>\n<li>ক্যামেরা আর জিনিসের মাঝে <b>এক হাত (আধা মিটার)</b> দূরত্ব রাখুন।</li>\n<li>শব্দ শুনতে সমস্যা হলে সেটিংসে গিয়ে <b>কণ্ঠের গতি</b> কমিয়ে নিন।</li>\n<li>স্ক্রিন রিডার (TalkBack) চালু থাকলেও আলোক কাজ করে — ঘোষণাগুলো লেখা হিসেবেও দেখায়, তাই TalkBack সেগুলোও পড়ে শোনাতে পারে।</li>',
      en: '<li>Use good light — daylight or a room lamp.</li>\n<li>Keep <b>about an arm’s length (half a meter)</b> between the camera and the object.</li>\n<li>If speech is hard to follow, lower the <b>voice speed</b> in Settings.</li>\n<li>Alok works alongside a screen reader (TalkBack) — announcements also appear as text, so TalkBack can read them too.</li>',
    },
    'help.s4.h':   { bn: 'ফোনে অ্যাপ হিসেবে রাখা', en: 'Installing it like an app' },
    'help.s4.body': {
      bn: '<li>Chrome-এ এই ঠিকানা খুলুন।</li>\n<li>উপরে ডানদিকের মেনু (⋮) চাপুন।</li>\n<li><b>"Add to Home screen"</b> বেছে নিন।</li>',
      en: '<li>Open this address in Chrome.</li>\n<li>Tap the menu (⋮) in the top-right corner.</li>\n<li>Choose <b>"Add to Home screen"</b>.</li>',
    },
    'help.s4.note': {
      bn: 'এরপর হোম স্ক্রিনের <b>আলোক</b> আইকন থেকেই অ্যাপের মতো খুলবে — অ্যাপ স্টোর লাগবে না, টাকাও লাগবে না।',
      en: 'From then on, the <b>Alok</b> icon on your home screen opens it like an app — no app store, no cost.',
    },
    'help.about.h': { bn: 'প্রকল্প সম্পর্কে', en: 'About' },
    'help.about.body': {
      bn: 'আলোক দৃষ্টিপ্রতিবন্ধী বাংলাভাষী মানুষের জন্য একটি ওপেন সোর্স সহায়ক অ্যাপ। দুটি YOLO11 মডেল (বাংলাদেশি টাকার নোটে প্রশিক্ষিত কাস্টম মডেল + ৮০ শ্রেণির সাধারণ মডেল) সার্ভারে চলে; ঘোষণা তৈরি হয় দিক, দূরত্ব ও নিশ্চয়তাসহ বাংলায়, আর সেগুলো বলে ফোনের নিজের কণ্ঠ। <a href="/docs">API ডকুমেন্টেশন</a>।',
      en: 'Alok is an open-source assistive vision app for blind and low-vision Bangla speakers. A YOLO11 model pair (custom-trained on Bangladeshi banknotes + a general 80-class model) runs on the server; announcements are generated in Bangla with direction, proximity, and confidence hedging, and spoken by the phone’s own text-to-speech. <a href="/docs">API documentation</a>.',
    },
  };

  function getLang() {
    const stored = localStorage.getItem('alok-lang');
    return stored === 'en' ? 'en' : 'bn';
  }

  function t(key, params) {
    const entry = STRINGS[key];
    let s = entry ? (entry[getLang()] || entry.bn) : key;
    if (params) {
      for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, v);
    }
    return s;
  }

  function applyLang() {
    const lang = getLang();
    document.documentElement.lang = lang;

    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const entry = STRINGS[el.dataset.i18n];
      if (entry) el.innerHTML = entry[lang] || entry.bn;
    });
    document.querySelectorAll('[data-i18n-aria]').forEach((el) => {
      const entry = STRINGS[el.dataset.i18nAria];
      if (entry) el.setAttribute('aria-label', entry[lang] || entry.bn);
    });
    document.querySelectorAll('[data-i18n-alt]').forEach((el) => {
      const entry = STRINGS[el.dataset.i18nAlt];
      if (entry) el.setAttribute('alt', entry[lang] || entry.bn);
    });

    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      // The button shows the language you would switch TO
      toggle.textContent = lang === 'bn' ? 'English' : 'বাংলা';
      toggle.setAttribute('aria-label',
        lang === 'bn' ? 'Switch to English' : 'বাংলায় দেখুন');
    }

    document.dispatchEvent(new CustomEvent('alok:langchange', { detail: { lang } }));
  }

  function setLang(lang) {
    localStorage.setItem('alok-lang', lang === 'en' ? 'en' : 'bn');
    applyLang();
  }

  // Extend the shared namespace
  window.Alok = window.Alok || {};
  Object.assign(window.Alok, { t, getLang, setLang, applyLang });

  document.addEventListener('DOMContentLoaded', () => {
    applyLang();
    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => setLang(getLang() === 'bn' ? 'en' : 'bn'));
    }
  });
})();
