"""
Remap class ids in YOLO label files so an external dataset (e.g. NSTU-BDTAKA)
matches this project's class order:

    0='1 Taka' 1='10 Taka' 2='100 Taka' 3='1000 Taka' 4='2 Taka'
    5='20 Taka' 6='200 Taka' 7='5 Taka' 8='50 Taka' 9='500 Taka'

1. Open the external dataset's data.yaml and note ITS class order.
2. Build the mapping "their id -> our id" and pass it as pairs.
3. Classes the external set has but ours doesn't (e.g. coins): map to 'drop'.

Example — external yaml says {0: '10 Taka', 1: '100 Taka', 2: 'coin'}:

    python tools/remap_labels.py --labels path/to/labels/train \
        --map 0:1 1:2 2:drop

Rewrites the .txt files in place (keeps a .bak copy of each on first run).
"""

import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--labels', required=True, help='folder of YOLO .txt label files')
    ap.add_argument('--map', nargs='+', required=True,
                    help="pairs like 0:1 1:2 2:drop (their_id:our_id or their_id:drop)")
    args = ap.parse_args()

    mapping = {}
    for pair in args.map:
        src, dst = pair.split(':')
        mapping[int(src)] = None if dst.lower() == 'drop' else int(dst)

    labels_dir = Path(args.labels)
    files = sorted(labels_dir.glob('*.txt'))
    if not files:
        raise SystemExit(f"No .txt label files in {labels_dir}")

    changed = dropped = 0
    for f in files:
        out_lines = []
        for line in f.read_text().splitlines():
            parts = line.split()
            if not parts:
                continue
            cid = int(parts[0])
            if cid not in mapping:
                raise SystemExit(
                    f"{f.name}: class id {cid} has no mapping — add '{cid}:<our_id>' or '{cid}:drop'")
            new_id = mapping[cid]
            if new_id is None:
                dropped += 1
                continue
            out_lines.append(' '.join([str(new_id)] + parts[1:]))

        bak = f.with_suffix('.txt.bak')
        if not bak.exists():
            bak.write_text(f.read_text())
        f.write_text('\n'.join(out_lines) + ('\n' if out_lines else ''))
        changed += 1

    print(f"Remapped {changed} label files ({dropped} boxes dropped). Backups: *.txt.bak")


if __name__ == '__main__':
    main()
