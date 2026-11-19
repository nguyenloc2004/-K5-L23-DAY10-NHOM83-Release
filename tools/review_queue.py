#!/usr/bin/env python3
"""Chia hàng đợi ứng viên cho cả nhóm và gộp kết quả review (Người 3). Chỉ thư viện chuẩn.

  # 1. chia: mỗi người một file review_<tên>.csv, ảnh của cùng một ảnh luôn về cùng một người
  py -X utf8 tools/review_queue.py split runs/r83/candidates.json --out runs/r83/review
  # 2. mỗi người mở file của mình, xem ảnh (tools/view.py --review ...), điền verdict + note
  # 3. gộp + kiểm: ra review_log.csv đúng mẫu image,type,verdict,note
  py -X utf8 tools/review_queue.py merge runs/r83/review --out runs/r83/review_log.csv

verdict: confirmed | rejected.  note: >= 20 ký tự, nói THẤY GÌ trong ảnh; tên người xem tự thêm ở đầu note.
Nếu xem ảnh thấy loại lỗi khác ứng viên gợi ý (vd. gợi ý class_swap nhưng thực ra panoptic sai),
sửa cột type thành loại đúng (category_swap) rồi mới confirmed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REVIEWERS = ["baodu1204", "Hung-1812", "nguyenloc2004", "zenlylove"]
SEMANTIC = {"class_swap", "bbox_drift", "missing_box", "category_swap", "instance_merge"}
FIELDS = ["image", "type", "verdict", "note", "hint"]


def load_candidates(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))  # utf-8-sig: chịu được BOM do PowerShell ghi
    rows = doc.get("candidates", doc) if isinstance(doc, dict) else doc
    out = []
    for r in rows:
        stem = r.get("image") or r.get("target")
        if not stem:
            continue
        hint = " · ".join(f"{k}={r[k]}" for k in ("det_class", "pan_class", "score", "reason") if r.get(k) not in (None, ""))
        out.append({"image": stem, "type": r.get("type", ""), "hint": hint})
    return out


def split(args) -> int:
    rows = load_candidates(Path(args.candidates))
    by_image: dict[str, list[dict]] = {}
    for r in rows:
        by_image.setdefault(r["image"], []).append(r)
    people = args.people.split(",") if args.people else REVIEWERS
    load = {p: [] for p in people}
    # ảnh nhiều ứng viên chia trước, luôn đưa cho người đang ít việc nhất
    for stem in sorted(by_image, key=lambda s: (-len(by_image[s]), s)):
        who = min(people, key=lambda p: len(load[p]))
        load[who] += by_image[stem]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for who, items in load.items():
        p = out / f"review_{who}.csv"
        if p.exists() and not args.force:
            print(f"BỎ QUA {p}: đã có (có thể đã điền). Thêm --force để ghi đè.")
            continue
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for it in sorted(items, key=lambda r: (r["image"], r["type"])):
                note = f"[{who}] " if len(people) > 1 else ""  # 1 người làm thì không cần ghi tên
                w.writerow({"image": it["image"], "type": it["type"], "verdict": "", "note": note, "hint": it["hint"]})
        print(f"{p}: {len(items)} ứng viên / {len({i['image'] for i in items})} ảnh")
    print(f"Tổng {len(rows)} ứng viên trên {len(by_image)} ảnh.")
    return 0


def merge(args) -> int:
    files = sorted(Path(args.folder).glob("review_*.csv"))
    if not files:
        raise SystemExit(f"Không có review_*.csv trong {args.folder}")
    rows, problems = [], []
    for p in files:
        with p.open(encoding="utf-8-sig", newline="") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                img, typ = (r.get("image") or "").strip(), (r.get("type") or "").strip()
                verdict, note = (r.get("verdict") or "").strip().lower(), (r.get("note") or "").strip()
                where = f"{p.name}:{i} {img}"
                if verdict not in ("confirmed", "rejected"):
                    problems.append(f"{where}: chưa có verdict (confirmed/rejected)")
                    continue
                if typ not in SEMANTIC:
                    problems.append(f"{where}: type '{typ}' không phải lỗi gán nhãn")
                    continue
                if len(note) < 20:
                    problems.append(f"{where}: note < 20 ký tự, phải nói thấy gì")
                rows.append({"image": img, "type": typ, "verdict": verdict, "note": note})
    notes = [r["note"] for r in rows]
    if notes and len(set(notes)) < 0.7 * len(notes):
        problems.append(f"Chỉ {len(set(notes))}/{len(notes)} note khác nhau (check_handover H3 cần >= 70%)")
    dup = {}
    for r in rows:
        dup.setdefault((r["image"], r["type"]), []).append(r["verdict"])
    problems += [f"{k}: có cả confirmed và rejected" for k, v in dup.items() if len(set(v)) > 1]
    conf_per_img = {}
    for r in rows:
        if r["verdict"] == "confirmed":
            conf_per_img.setdefault(r["image"], []).append(r["type"])
    problems += [f"{img}: confirmed {len(t)} lỗi {t} — mỗi ảnh tối đa 1 lỗi, chọn một"
                 for img, t in conf_per_img.items() if len(set(t)) > 1]

    for p in problems:
        print("  !", p)
    if problems and not args.force:
        print(f"\n{len(problems)} vấn đề. Sửa rồi chạy lại (hoặc --force để vẫn ghi).")
        return 1
    seen = set()
    out_rows = []
    for r in sorted(rows, key=lambda r: (r["image"], r["type"])):
        if (r["image"], r["type"], r["verdict"]) not in seen:
            seen.add((r["image"], r["type"], r["verdict"]))
            out_rows.append(r)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "type", "verdict", "note"])
        w.writeheader()
        w.writerows(out_rows)
    c = sum(r["verdict"] == "confirmed" for r in out_rows)
    print(f"{args.out}: {len(out_rows)} dòng ({c} confirmed, {len(out_rows) - c} rejected) từ {len(files)} file")
    print("Tiếp: py -X utf8 scripts/merge_review.py --rules <rules.json> --review " + args.out + " --out <errors.json>")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Chia / gộp hàng đợi review")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("candidates")
    s.add_argument("--out", required=True, help="thư mục chứa review_<tên>.csv")
    s.add_argument("--people", help="danh sách tên, phẩy ngăn cách (mặc định 4 thành viên)")
    s.add_argument("--force", action="store_true")
    m = sub.add_parser("merge")
    m.add_argument("folder")
    m.add_argument("--out", required=True)
    m.add_argument("--force", action="store_true")
    args = ap.parse_args()
    return split(args) if args.cmd == "split" else merge(args)


if __name__ == "__main__":
    sys.exit(main())
