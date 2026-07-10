"""
Synthetic training data generator for the Alok banknote model.

Banknotes are flat and rigid, so a handful of clean photos per denomination
can be composited into thousands of realistic, automatically-labeled training
images: random backgrounds, perspective, rotation, lighting, blur, shadows,
and finger occlusion — mimicking exactly what a phone camera sees in live use.

Input layout (a few images per class are enough — even 3-5 each):

    raw_notes/
        1 Taka/    *.jpg  (each image: one note, photographed fairly tight)
        10 Taka/   *.jpg
        ...
        1000 Taka/ *.jpg

Optional: --backgrounds folder with any photos (rooms, streets, tables).
Without it, procedural backgrounds (textures/gradients) are generated.

Output: a ready-to-train YOLO dataset:

    synth_dataset/
        images/train, images/val
        labels/train, labels/val
        data.yaml

Usage:
    python tools/synthesize_dataset.py --notes raw_notes --count 2000
    yolo detect train data=synth_dataset/data.yaml model=backend/detection/best.pt epochs=80 imgsz=640
"""

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

# Must match the class order of backend/detection/best.pt
CLASSES = ['1 Taka', '10 Taka', '100 Taka', '1000 Taka', '2 Taka',
           '20 Taka', '200 Taka', '5 Taka', '50 Taka', '500 Taka']

CANVAS = 640  # output image size


# --------------------------------------------------------------------------
# Backgrounds
# --------------------------------------------------------------------------

def procedural_background():
    """Random texture/gradient background when no photo folder is given."""
    kind = random.choice(['noise', 'gradient', 'flat', 'blotch'])
    if kind == 'flat':
        color = np.random.randint(30, 220, 3)
        bg = np.full((CANVAS, CANVAS, 3), color, np.uint8)
    elif kind == 'gradient':
        a = np.random.randint(0, 255, 3).astype(float)
        b = np.random.randint(0, 255, 3).astype(float)
        t = np.linspace(0, 1, CANVAS)[:, None]
        col = (a * (1 - t) + b * t).astype(np.uint8)          # (CANVAS, 3)
        bg = np.repeat(col[:, None, :], CANVAS, axis=1)
        if random.random() < 0.5:
            bg = cv2.rotate(bg, cv2.ROTATE_90_CLOCKWISE)
    elif kind == 'blotch':
        small = np.random.randint(0, 255, (8, 8, 3), np.uint8)
        bg = cv2.resize(small, (CANVAS, CANVAS), interpolation=cv2.INTER_CUBIC)
    else:
        bg = np.random.randint(0, 255, (CANVAS, CANVAS, 3), np.uint8)
        bg = cv2.GaussianBlur(bg, (0, 0), random.uniform(2, 8))
    # gentle texture noise on top
    noise = np.random.normal(0, 6, bg.shape).astype(np.int16)
    return np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def photo_background(bg_files):
    img = cv2.imread(str(random.choice(bg_files)))
    if img is None:
        return procedural_background()
    h, w = img.shape[:2]
    # random square crop, resized to canvas
    side = min(h, w)
    crop = random.randint(side // 2, side)
    y = random.randint(0, h - crop)
    x = random.randint(0, w - crop)
    return cv2.resize(img[y:y + crop, x:x + crop], (CANVAS, CANVAS))


# --------------------------------------------------------------------------
# Note transformation
# --------------------------------------------------------------------------

def warp_note(note):
    """Random scale, rotation, and perspective. Returns (warped_bgr, mask)."""
    h, w = note.shape[:2]

    # target width on the canvas: prominent (close) to smallish (arm's length)
    target_w = random.uniform(0.35, 0.85) * CANVAS
    scale = target_w / w
    note = cv2.resize(note, (int(w * scale), int(h * scale)))
    h, w = note.shape[:2]

    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    # perspective jitter: each corner moves up to 12% — a tilted hand-held note
    jitter = 0.12
    dst = src + np.random.uniform(-jitter, jitter, src.shape).astype(np.float32) * [[w, h]]

    angle = random.uniform(-35, 35)
    m_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    dst = cv2.transform(dst[None], m_rot)[0].astype(np.float32)

    # bounding canvas of the warped result
    min_xy = dst.min(axis=0)
    dst -= min_xy
    out_w, out_h = int(dst[:, 0].max()) + 1, int(dst[:, 1].max()) + 1
    if out_w < 8 or out_h < 8 or out_w > CANVAS or out_h > CANVAS:
        return None, None

    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(note, matrix, (out_w, out_h))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), matrix, (out_w, out_h))
    return warped, mask


def add_finger_occlusion(canvas, mask_region):
    """Cover part of the note with a skin-toned ellipse — a holding thumb."""
    x, y, w, h = mask_region
    cx = random.choice([x, x + w])                # a finger comes from an edge
    cy = random.randint(y, y + h)
    axes = (random.randint(w // 8, w // 4), random.randint(h // 6, h // 3))
    skin = (
        random.randint(70, 130),   # B
        random.randint(100, 160),  # G
        random.randint(150, 220),  # R
    )
    cv2.ellipse(canvas, (cx, cy), axes, random.uniform(0, 180), 0, 360, skin, -1)


def photometric(img):
    """Lighting, blur, and sensor effects a webcam produces."""
    img = img.astype(np.float32)
    img = img * random.uniform(0.55, 1.35) + random.uniform(-25, 25)   # exposure
    img = np.clip(img, 0, 255).astype(np.uint8)

    # color temperature shift
    shift = np.random.uniform(-14, 14, 3)
    img = np.clip(img.astype(np.float32) + shift, 0, 255).astype(np.uint8)

    r = random.random()
    if r < 0.25:                                       # gaussian blur
        img = cv2.GaussianBlur(img, (0, 0), random.uniform(0.6, 1.8))
    elif r < 0.45:                                     # motion blur
        k = random.choice([5, 7, 9])
        kernel = np.zeros((k, k), np.float32)
        kernel[k // 2, :] = 1.0 / k
        m = cv2.getRotationMatrix2D((k / 2, k / 2), random.uniform(0, 180), 1)
        kernel = cv2.warpAffine(kernel, m, (k, k))
        img = cv2.filter2D(img, -1, kernel)

    if random.random() < 0.4:                          # sensor noise
        noise = np.random.normal(0, random.uniform(2, 7), img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    if random.random() < 0.5:                          # jpeg artifacts
        q = random.randint(40, 85)
        _, enc = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return img


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------

def compose(note_img, cls_id, extra_notes):
    """One synthetic image. Returns (image, list of yolo label lines)."""
    bg = compose.background()
    labels = []

    placements = [(note_img, cls_id)] + extra_notes
    for img, cid in placements:
        warped, mask = warp_note(img)
        if warped is None:
            continue
        oh, ow = warped.shape[:2]
        x = random.randint(0, CANVAS - ow)
        y = random.randint(0, CANVAS - oh)

        roi = bg[y:y + oh, x:x + ow]
        m = (mask > 0)

        if random.random() < 0.6:                      # soft drop shadow
            shadow = np.zeros((oh, ow), np.uint8)
            shadow[m] = 90
            shadow = cv2.GaussianBlur(shadow, (0, 0), 6)
            off = random.randint(3, 8)
            sy, sx = min(y + off, CANVAS - oh), min(x + off, CANVAS - ow)
            region = bg[sy:sy + oh, sx:sx + ow].astype(np.int16)
            bg[sy:sy + oh, sx:sx + ow] = np.clip(region - shadow[..., None], 0, 255).astype(np.uint8)
            roi = bg[y:y + oh, x:x + ow]

        roi[m] = warped[m]

        # tight bbox from the mask
        ys, xs = np.where(m)
        x1, x2 = x + xs.min(), x + xs.max()
        y1, y2 = y + ys.min(), y + ys.max()

        if random.random() < 0.45:
            add_finger_occlusion(bg, (x1, y1, x2 - x1, y2 - y1))

        cx = (x1 + x2) / 2 / CANVAS
        cy = (y1 + y2) / 2 / CANVAS
        bw = (x2 - x1) / CANVAS
        bh = (y2 - y1) / CANVAS
        labels.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    return photometric(bg), labels


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--notes', required=True, help='folder with one subfolder per class of note photos')
    ap.add_argument('--backgrounds', default=None, help='optional folder of background photos')
    ap.add_argument('--out', default='synth_dataset', help='output dataset folder')
    ap.add_argument('--count', type=int, default=2000, help='number of images to generate')
    ap.add_argument('--val-split', type=float, default=0.1)
    args = ap.parse_args()

    notes_dir = Path(args.notes)
    sources = {}  # cls_id -> [images]
    for cid, cname in enumerate(CLASSES):
        files = sorted((notes_dir / cname).glob('*')) if (notes_dir / cname).is_dir() else []
        imgs = [cv2.imread(str(f)) for f in files]
        imgs = [i for i in imgs if i is not None]
        if imgs:
            sources[cid] = imgs
        print(f"  {cname}: {len(imgs)} source photo(s)")

    if not sources:
        raise SystemExit(f"No note photos found under {notes_dir}/<class name>/")

    bg_files = list(Path(args.backgrounds).glob('**/*')) if args.backgrounds else []
    bg_files = [f for f in bg_files if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    compose.background = (lambda: photo_background(bg_files)) if bg_files else procedural_background
    print(f"Backgrounds: {'%d photos' % len(bg_files) if bg_files else 'procedural'}")

    out = Path(args.out)
    for sub in ('images/train', 'images/val', 'labels/train', 'labels/val'):
        (out / sub).mkdir(parents=True, exist_ok=True)

    class_ids = list(sources.keys())
    made = 0
    for i in range(args.count):
        cid = class_ids[i % len(class_ids)]          # perfectly balanced classes
        note = random.choice(sources[cid])

        # 25% of images contain a second, different note
        extra = []
        if random.random() < 0.25 and len(class_ids) > 1:
            cid2 = random.choice([c for c in class_ids if c != cid])
            extra.append((random.choice(sources[cid2]), cid2))

        img, labels = compose(note, cid, extra)
        if not labels:
            continue

        split = 'val' if random.random() < args.val_split else 'train'
        stem = f'synth_{i:06d}'
        cv2.imwrite(str(out / 'images' / split / f'{stem}.jpg'), img,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        (out / 'labels' / split / f'{stem}.txt').write_text('\n'.join(labels))
        made += 1
        if made % 200 == 0:
            print(f'  {made}/{args.count}')

    yaml = (
        f"path: {out.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"names: {dict(enumerate(CLASSES))}\n"
    )
    (out / 'data.yaml').write_text(yaml)
    print(f"\nDone: {made} images in {out}/ — train with:")
    print(f"  yolo detect train data={out}/data.yaml model=backend/detection/best.pt epochs=80 imgsz=640 patience=20")


if __name__ == '__main__':
    main()
