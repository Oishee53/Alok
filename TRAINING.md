# Improving banknote accuracy without collecting a big dataset

Three sources of training data, cheapest first. Mix all three for the best
result — the goal is a few thousand images that *look like what the live
camera actually sees*.

## 1. Synthetic data from the photos you already have

`tools/synthesize_dataset.py` turns a handful of note photos into thousands
of auto-labeled training images: random backgrounds, tilt, perspective,
lighting, blur, shadows, and finger occlusion.

```
raw_notes/
    1 Taka/     a few tightly-cropped photos of the note (3-5 is enough)
    10 Taka/
    ...
    1000 Taka/
```

```bash
cd backend && venv\Scripts\activate && cd ..
python tools/synthesize_dataset.py --notes raw_notes --count 3000
```

Optionally pass `--backgrounds <folder>` with any photos (rooms, streets,
tables) — real backgrounds beat procedural ones. Output goes to
`synth_dataset/` as a ready YOLO dataset with `data.yaml`.

Tip: photograph each note **both sides**, and if you can get them, both the
old and the new (2022+) series — that alone fixes a whole class of errors.

## 2. Free public datasets (thousands of labeled taka images)

- **NSTU-BDTAKA** — 3,111 detection images **already in YOLO format**
  (train/test/validation folders with images + labels), plus 28,875
  recognition images. Download: https://data.mendeley.com/datasets/w4y6h723xg/1
  Its class ids won't match this project's order — fix with
  `python tools/remap_labels.py --labels <their labels folder> --map ...`
  (open their data.yaml, map their ids to ours; see the script's docstring).
- **BanglaTaka** — 5,073 labeled images of 9 denominations (classification
  crops — perfect as *source photos* for the synthesizer above).
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12284552/
- **Kaggle: Bangla Money** — 1,970 images, 9 categories.
  https://www.kaggle.com/datasets/nsojib/bangla-money
- **Bangladeshi Currency (Coins & Notes)** — Mendeley:
  https://data.mendeley.com/datasets/xn44yz596n/2
- **A Diverse Image Dataset for Bangladeshi Currency Recognition** — Mendeley:
  https://data.mendeley.com/datasets/3cv2sypkkh/1
- Also search Roboflow Universe for "taka" / "bdt currency" — several
  community projects there export directly in YOLO format.

Watch the class order: this project's model uses
`['1 Taka', '10 Taka', '100 Taka', '1000 Taka', '2 Taka', '20 Taka',
'200 Taka', '5 Taka', '50 Taka', '500 Taka']` (see `synthesize_dataset.py`).
Map any external dataset's labels to these names/ids before merging.

## 3. Screenshots from the app itself

The most valuable images are the ones the model currently gets wrong. Use
live mode, and when a note is misread, save the frame. Fifty of these are
worth more than five hundred clean scans.

## Training (merging new data with your previous training)

Two ideas, don't confuse them:

- **Your previous training lives in `best.pt`.** Passing
  `model=backend/detection/best.pt` to `yolo train` continues from those
  weights (fine-tuning) — that's how the old training carries over.
- **But weights alone don't protect old knowledge.** Fine-tuning on only the
  new dataset makes the model drift toward it and forget your original
  images. So merge the *datasets* and run one training on everything.

No copying needed — Ultralytics accepts a list of train/val folders. Create
`combined.yaml` (labels are found automatically by replacing `images` with
`labels` in each path):

```yaml
# combined.yaml — every dataset you have, one training run
train:
  - D:/data/nstu/Detect/train/images        # NSTU-BDTAKA (after remap_labels.py!)
  - D:/data/my_original_dataset/images/train  # the data best.pt was trained on
  - D:/Code/Alok_v11/synth_dataset/images/train
val:
  - D:/data/nstu/Detect/validation/images
  - D:/Code/Alok_v11/synth_dataset/images/val
names:
  0: 1 Taka
  1: 10 Taka
  2: 100 Taka
  3: 1000 Taka
  4: 2 Taka
  5: 20 Taka
  6: 200 Taka
  7: 5 Taka
  8: 50 Taka
  9: 500 Taka
```

Every dataset in the list must already use THIS class order — that's what
`tools/remap_labels.py` is for. Then:

```bash
yolo detect train data=combined.yaml model=backend/detection/best.pt \
     epochs=80 imgsz=640 patience=20 batch=16
```

If you no longer have your original dataset, that's okay: starting from
`best.pt` still transfers most of what it learned, and NSTU + synthetic
data cover the gap. Prefer more real data over worrying about the old set.

- Your local venv has **CPU-only torch — training will be very slow**. Use a
  free GPU on Google Colab or Kaggle Notebooks: upload the dataset zip,
  `pip install ultralytics`, run the same command, download
  `runs/detect/train/weights/best.pt`.
- Small dataset rules: stay on the small model (yolo11n/11s — bigger ones
  overfit), keep default augmentation on, let `patience` stop it early.

## Check what's actually confused

```bash
yolo detect val data=synth_dataset/data.yaml model=<new best.pt>
```

Look at `confusion_matrix.png` in the run folder — it shows exactly which
denominations get mistaken for which, so you can add data where it matters
instead of guessing.

## Deploy the new model

Replace `backend/detection/best.pt` with the new weights and restart the
server. Nothing else needs to change (the app reads class names from the
model). If you deployed to Hugging Face, commit + push and it rebuilds.
