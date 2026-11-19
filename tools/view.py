#!/usr/bin/env python3
"""Công cụ xem ảnh cho review (Người 3). Dùng Pillow — CHỈ cho công cụ xem ảnh, validator không dùng.

Mỗi ảnh xuất ra một PNG ghép 2 khung cạnh nhau:
  - Trái : ảnh + box DETECTION (labels/*.txt), ghi tên lớp theo classes.txt
  - Phải : ảnh + viền segment PANOPTIC (masks/*.png + panoptic.json), ghi tên lớp theo categories
Ảnh nhỏ được phóng to (mặc định cạnh dài ~900 px). Box/segment trùng với ứng viên được tô đậm.

  # xem vài ảnh
  py -X utf8 tools/view.py runs/r83/delivery 000000000139 000000000285
  # xem toàn bộ hàng đợi ứng viên (hoặc chỉ phần của mình trong file review)
  py -X utf8 tools/view.py runs/r83/delivery --candidates runs/r83/candidates.json
  py -X utf8 tools/view.py runs/r83/delivery --review runs/r83/review/review_nguyenloc2004.csv
  # phóng to vùng quanh một vật (x0 y0 x1 y1 theo pixel ảnh gốc), mở ngay sau khi vẽ
  py -X utf8 tools/view.py runs/r83/delivery 000000000139 --crop 100 50 300 250 --open

Ảnh xuất ở <thư mục delivery>/../view/ (nằm trong runs/, không commit).
Cài Pillow một lần: py -m pip install --user pillow
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    raise SystemExit("Thiếu Pillow. Cài: py -m pip install --user pillow")

TARGET_LONG_SIDE = 900


# ------------------------------------------------------------------ đọc lô
class Delivery:
    def __init__(self, root: Path):
        self.root = root
        self.classes = {}
        for line in (root / "classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                cid, name = line.split(" ", 1)
                self.classes[int(cid)] = name.strip()
        pan = json.loads((root / "panoptic.json").read_text(encoding="utf-8"))
        self.cats = {c["id"]: c for c in pan["categories"]}
        self.img_by_id = {im["id"]: im for im in pan["images"]}
        self.ann_by_stem = {}
        for ann in pan["annotations"]:
            im = self.img_by_id.get(ann["image_id"], {})
            stem = Path(im.get("file_name") or ann["file_name"]).stem
            self.ann_by_stem[stem] = (im, ann)
        man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.manifest = man.get("items", man)

    def path(self, stem: str, kind: str, sub: str, ext: str) -> Path:
        item = self.manifest.get(stem, {})
        return self.root / item[kind] if kind in item else self.root / sub / f"{stem}{ext}"

    def boxes(self, stem: str, width: int, height: int) -> list[dict]:
        out = []
        p = self.path(stem, "label", "labels", ".txt")
        if not p.is_file():
            return out
        for ln in p.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if len(parts) < 5:
                continue
            try:
                cid = int(float(parts[0]))
                x, y, w, h = map(float, parts[1:5])
            except ValueError:
                continue
            out.append({"cls": cid, "name": self.classes.get(cid, f"?{cid}"),
                        "box": [(x - w / 2) * width, (y - h / 2) * height, (x + w / 2) * width, (y + h / 2) * height]})
        return out


# ------------------------------------------------------------------ vẽ
def color_for(name: str) -> tuple[int, int, int]:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16) / 0xFFFFFF
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tag(draw: ImageDraw.ImageDraw, xy, text: str, color, fnt):
    x, y = xy
    l, t, r, b = draw.textbbox((x, y), text, font=fnt)
    y = max(0, y - (b - t) - 4)
    draw.rectangle([x, y, x + (r - l) + 6, y + (b - t) + 4], fill=color)
    draw.text((x + 3, y + 1), text, fill=(0, 0, 0), font=fnt)


def segments(dl: Delivery, stem: str):
    """Trả về (ảnh id segment theo pixel dạng list, w, h, info theo id, bbox tính từ mask)."""
    mp = dl.path(stem, "mask", "masks", ".png")
    if not mp.is_file():
        return None
    mask = Image.open(mp).convert("RGB")
    w, h = mask.size
    data = mask.tobytes()
    ids = [data[i] + data[i + 1] * 256 + data[i + 2] * 65536 for i in range(0, len(data), 3)]
    _, ann = dl.ann_by_stem.get(stem, ({}, {"segments_info": []}))
    info = {s["id"]: s for s in ann.get("segments_info", [])}
    bbox, count = {}, {}
    for idx, sid in enumerate(ids):
        if not sid:
            continue
        x, y = idx % w, idx // w
        b = bbox.get(sid)
        if b is None:
            bbox[sid] = [x, y, x, y]
        else:
            b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)
        count[sid] = count.get(sid, 0) + 1
    return ids, w, h, info, bbox, count


def render(dl: Delivery, stem: str, notes: list[str], highlight: list[dict], crop, out_dir: Path) -> Path:
    img_path = dl.path(stem, "image", "images", ".jpg")
    seg = segments(dl, stem)
    if img_path.is_file():
        base = Image.open(img_path).convert("RGB")
    elif seg:
        base = Image.new("RGB", (seg[1], seg[2]), (40, 40, 40))
        notes = notes + ["KHÔNG CÓ FILE ẢNH (missing_image?)"]
    else:
        raise SystemExit(f"{stem}: không có ảnh lẫn mask")
    W, H = base.size
    if seg and (seg[1], seg[2]) != (W, H):
        notes = notes + [f"Cảnh báo: mask {seg[1]}x{seg[2]} khác ảnh {W}x{H}"]

    x0, y0, x1, y1 = (0, 0, W, H) if not crop else [max(0, crop[0]), max(0, crop[1]), min(W, crop[2]), min(H, crop[3])]
    scale = TARGET_LONG_SIDE / max(x1 - x0, y1 - y0)
    scale = max(scale, 1.0)

    def tr(px, py):
        return (px - x0) * scale, (py - y0) * scale

    size = (int((x1 - x0) * scale), int((y1 - y0) * scale))
    fnt = font(max(12, int(13 * min(scale, 2))))
    hl_boxes = [h.get("box_px") for h in highlight if h.get("box_px")]
    hl_segs = {h.get("segment_id") for h in highlight if h.get("segment_id") is not None}

    # --- khung trái: detection
    left = base.crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
    dl_draw = ImageDraw.Draw(left)
    for i, b in enumerate(dl.boxes(stem, W, H)):
        c = color_for(b["name"])
        bx = b["box"]
        hit = any(hb and all(abs(bx[k] - hb[k]) < 3 for k in range(4)) for hb in hl_boxes)
        p0, p1 = tr(bx[0], bx[1]), tr(bx[2], bx[3])
        dl_draw.rectangle([p0, p1], outline=(255, 255, 255) if hit else c, width=5 if hit else 2)
        tag(dl_draw, p0, f"#{i} {b['name']}" + (" ◄" if hit else ""), c, fnt)
    for hb in hl_boxes:  # ứng viên có box_px không trùng box nào (vd. missing_box) vẫn vẽ nét đứt
        p0, p1 = tr(hb[0], hb[1]), tr(hb[2], hb[3])
        dl_draw.rectangle([p0, p1], outline=(255, 255, 255), width=1)

    # --- khung phải: panoptic
    right = base.crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
    if seg:
        ids, mw, mh, info, bbox, count = seg
        overlay = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
        opx = overlay.load()
        for idx, sid in enumerate(ids):
            if not sid:
                continue
            x, y = idx % mw, idx // mw
            s = info.get(sid)
            if s is None or not dl.cats.get(s["category_id"], {}).get("isthing"):
                continue  # chỉ tô thing; stuff (trời, đường…) để trơn cho dễ nhìn
            right_id = ids[idx + 1] if x + 1 < mw else -1
            down_id = ids[idx + mw] if y + 1 < mh else -1
            c = color_for(dl.cats.get(s["category_id"], {}).get("name", "?"))
            if right_id != sid or down_id != sid:
                opx[x, y] = (*c, 255) if sid not in hl_segs else (255, 255, 255, 255)
            else:
                opx[x, y] = (*c, 70 if sid not in hl_segs else 120)
        overlay = overlay.crop((x0, y0, x1, y1)).resize(size, Image.NEAREST)
        right = Image.alpha_composite(right.convert("RGBA"), overlay).convert("RGB")
        rd = ImageDraw.Draw(right)
        for sid, s in info.items():
            cat = dl.cats.get(s["category_id"])
            if not cat or not cat.get("isthing") or sid not in bbox:
                continue
            b = bbox[sid]
            name = cat["name"] + (" (crowd)" if s.get("iscrowd") else "")
            extra = f" area={s.get('area')}/px={count.get(sid, 0)}"
            tag(rd, tr(b[0], b[1]), name + (extra if sid in hl_segs else "") + (" ◄" if sid in hl_segs else ""),
                color_for(cat["name"]), fnt)
        for s in info.values():  # category_id không có trong categories
            if s["category_id"] not in dl.cats:
                notes = notes + [f"segment {s['id']}: category_id {s['category_id']} KHÔNG có trong categories"]

    # --- ghép + chú thích
    head = [f"{stem}   ({W}x{H}, phóng {scale:.1f}x)   TRÁI = detection   PHẢI = panoptic (chỉ thing)"] + notes
    hfnt = font(15)
    line_h = 22
    canvas = Image.new("RGB", (size[0] * 2 + 10, size[1] + line_h * len(head) + 10), (20, 20, 20))
    cd = ImageDraw.Draw(canvas)
    for i, text in enumerate(head):
        cd.text((8, 5 + i * line_h), text, fill=(255, 255, 255), font=hfnt)
    top = line_h * len(head) + 10
    canvas.paste(left, (0, top))
    canvas.paste(right, (size[0] + 10, top))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stem}.png"
    canvas.save(out)
    return out


# ------------------------------------------------------------------ hàng đợi
def load_candidates(path: Path) -> dict[str, list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))  # utf-8-sig: chịu được BOM do PowerShell ghi
    rows = doc.get("candidates", doc) if isinstance(doc, dict) else doc
    out: dict[str, list[dict]] = {}
    for r in rows:
        stem = r.get("image") or r.get("target")
        if stem:
            out.setdefault(stem, []).append(r)
    return out


def describe(c: dict) -> str:
    keys = ("type", "det_class", "pan_class", "score", "reason")
    return " · ".join(f"{k}={c[k]}" for k in keys if c.get(k) not in (None, ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="Vẽ detection | panoptic cạnh nhau để review")
    ap.add_argument("delivery")
    ap.add_argument("images", nargs="*", help="tên ảnh (không đuôi)")
    ap.add_argument("--candidates", help="candidates.json: vẽ mọi ảnh trong hàng đợi")
    ap.add_argument("--review", help="file review CSV (image,type,...): vẽ các ảnh trong file")
    ap.add_argument("--crop", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"), help="chỉ vẽ vùng này (pixel ảnh gốc)")
    ap.add_argument("--out", help="thư mục ảnh xuất (mặc định <delivery>/../view)")
    ap.add_argument("--open", action="store_true", help="mở ảnh sau khi vẽ (Windows/macOS)")
    args = ap.parse_args()

    root = Path(args.delivery)
    dl = Delivery(root)
    out_dir = Path(args.out) if args.out else root.parent / "view"
    cands = load_candidates(Path(args.candidates)) if args.candidates else {}
    todo = list(args.images) + [s for s in cands if s not in args.images]
    if args.review:
        with open(args.review, encoding="utf-8-sig", newline="") as f:
            todo += [r["image"].strip() for r in csv.DictReader(f) if r.get("image", "").strip() not in todo]
        if not cands:
            # tự tìm candidates.json cạnh thư mục delivery để có thông tin highlight
            guess = root.parent / "candidates.json"
            cands = load_candidates(guess) if guess.is_file() else {}
    if not todo:
        ap.error("cần tên ảnh, --candidates hoặc --review")

    for stem in dict.fromkeys(todo):
        hl = cands.get(stem, [])
        out = render(dl, stem, [describe(c) for c in hl], hl, args.crop, out_dir)
        print(out)
        if args.open:
            if sys.platform.startswith("win"):
                os.startfile(out)  # noqa: S606
            elif sys.platform == "darwin":
                os.system(f'open "{out}"')
    print(f"\n{len(dict.fromkeys(todo))} ảnh -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
