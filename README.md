# আলোক (Alok)

**যা দেখা যায় না, তা শোনা যায়।** — *What can't be seen can be heard.*

Alok is a free assistive-vision web app for blind and low-vision Bangla
speakers. Point a phone camera at the world and Alok speaks — in Bangla —
what it sees: which object, which direction, how close. It recognizes all
ten Bangladeshi banknote denominations (৳1–৳1000), 80+ everyday objects,
and reads printed Bangla and English text aloud.

**Live app:** https://alok-qf4t.onrender.com — open it in Chrome on a
phone, then *menu (⋮) → Add to Home screen* to install it like an app.
No app store, no account, no cost.

## Features

- **লাইভ (Live)** — continuous camera detection. Announcements include
  direction ("বাম দিকে / সামনে / ডান দিকে") and proximity ("খুব কাছে"),
  spoken by the phone's own Bangla voice. When the model is unsure it says
  **"সম্ভবত"** (possibly) instead of faking confidence.
- **Banknote recognition** — a custom-trained YOLO11 model identifies
  every taka note. Denomination *voting* across video frames prevents one
  blurry frame from announcing a wrong amount: the value is only spoken
  once several frames agree.
- **পড়ুন (Read)** — hold up a medicine label, newspaper, or book page and
  one tap reads it aloud in whichever language it's written. Uses Gemini
  OCR via the server when available (excellent Bangla accuracy), falling
  back to fully on-device Tesseract.js when offline.
- **Accessible by design** — screen-reader landmarks and live regions,
  64px+ touch targets, amber-on-black high-contrast palette (the tactile
  paving color pair), vibration feedback, and a bilingual UI (Bangla
  default, English toggle).
- **Installable PWA** — works from the browser, installs to the home
  screen, and the app shell loads offline.

## How it works

```
Phone (PWA)                              Server (FastAPI)
───────────                              ────────────────
camera frame ──JPEG over WebSocket──▶    dual YOLO11 inference
                                         (custom banknote model +
speaks the announcement  ◀──JSON──       general 80-class model),
via Web Speech API                       direction/proximity/hedging,
(bn voice; server gTTS                   denomination voting,
fallback for desktops)                   Bangla announcement text
```

- Detection runs server-side (two YOLO11 models merged per frame, with
  banknote-portrait suppression so faces printed on notes aren't announced
  as people). Speech happens **on the phone** — instant and free.
- Read mode's OCR runs on the phone (Tesseract.js WASM) or via the
  server's Gemini proxy when a free API key is configured.

## Run locally

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows (source venv/bin/activate on Linux)
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000 — frontend, API, and docs (`/docs`) are all
served from there. Phone camera access requires HTTPS, so for phone
testing use the deployed URL or a tunnel
(`cloudflared tunnel --url http://localhost:8000`).

## Deployment

The included `Dockerfile` runs anywhere (CPU-only torch, binds `$PORT`,
port 7860 fallback). `render.yaml` configures Render's free tier.

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `ALOK_IMGSZ` | `640` | Inference resolution. Use `320` on very weak CPUs (Render free = 0.1 vCPU) — ~4× less compute, slightly shorter range. |
| `ALOK_LITE` | off | `true` drops the general model (banknotes only) if the host runs out of memory. |
| `GEMINI_API_KEY` | unset | Free key from [aistudio.google.com](https://aistudio.google.com) — enables high-quality Bangla OCR in Read mode. |

Free-tier realities: Render free instances sleep after ~15 idle minutes
(~1 min wake-up) and detection runs at a few seconds per frame on 0.1 CPU.

## Improving the model

The banknote model improves with data that looks like real use — notes in
hand, webcam light, both note series. See **[TRAINING.md](TRAINING.md)**
for the full recipe, including free public datasets (NSTU-BDTAKA and
others) and the included tools:

- `tools/synthesize_dataset.py` — turns a few note photos into thousands
  of auto-labeled, realistically-degraded training images
- `tools/remap_labels.py` — aligns external datasets' class ids with this
  project's class order

## Project structure

```
backend/
  main.py                  FastAPI app; serves the frontend + API
  routes/detect_route.py   detection endpoints, WebSocket, TTS + OCR proxies
  detection/               YOLO models, Bangla announcer, denomination voting
frontend/
  index.html / live.html / read.html / help.html
  js/                      camera loop, speech queue, i18n, OCR
  sw.js                    offline shell (PWA)
Dockerfile, render.yaml    deployment
tools/, TRAINING.md        model improvement
```

## Roadmap

- On-device inference (TFLite export + Flutter) so live mode works fully
  offline with zero server cost
- Retraining on NSTU-BDTAKA + synthetic data for denomination accuracy
- Bill-side (front/back) awareness, pending side-labeled training data
