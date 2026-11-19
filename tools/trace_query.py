#!/usr/bin/env python3
"""Truy vết ticket của team AI -> trace.json (Người 3). Chỉ thư viện chuẩn, chỉ đọc thư mục delivery.

  py -X utf8 tools/trace_query.py runs/r83/delivery --out runs/r83/trace.json
  py -X utf8 tools/trace_query.py delivery --out submission/de_an/trace.json        # đề ẩn

Tiêu chí (GUIDE Pha 5, docs/DELIVERY mục 3):
  rule_class : lớp bị đổi quy tắc, đọc từ guideline/changelog.md (bản mới nhất) và đối chiếu ticket.
  job cũ     : job có guideline (ghi ở jobs.csv, KHÔNG lấy guideline_version của ảnh) cũ hơn bản đổi quy tắc.
  có lớp     : labels/<ảnh>.txt có ít nhất một box detection với class_id hợp lệ là rule_class.
  tier_a     : ảnh job cũ, có lớp, thuộc các scene ticket nêu.
  tier_b     : ảnh job cũ, có lớp, ở scene khác (chưa ai báo).
  notify     : annotator + reviewer của các job chứa ảnh tier_a và tier_b.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def version_key(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def parse_changelog(text: str) -> tuple[str, str]:
    """Trả về (phiên bản đổi quy tắc, tên lớp). Lấy mục '## vX' mới nhất có nhắc tới một lớp trong `...`."""
    sections = re.split(r"^##\s+", text, flags=re.M)[1:]
    found = []
    for sec in sections:
        head, _, body = sec.partition("\n")
        ver = head.strip().split()[0]
        classes = re.findall(r"[Ll]ớp\s+`([^`]+)`", body) or re.findall(r"`([^`]+)`", body)
        if classes:
            found.append((version_key(ver), ver, classes[0]))
    if not found:
        raise SystemExit("Không tìm thấy lớp bị đổi quy tắc trong changelog.md")
    found.sort()
    return found[-1][1], found[-1][2]


def main() -> int:
    ap = argparse.ArgumentParser(description="Truy vết ticket -> trace.json")
    ap.add_argument("delivery")
    ap.add_argument("--out", required=True)
    ap.add_argument("--class", dest="cls", help="ép tên lớp (mặc định đọc từ changelog)")
    args = ap.parse_args()
    d = Path(args.delivery)

    # 1. lớp đổi quy tắc + phiên bản đổi
    change_ver, rule_class = parse_changelog((d / "guideline" / "changelog.md").read_text(encoding="utf-8"))
    ticket = (d / "incoming" / "ticket.md").read_text(encoding="utf-8")
    ticket_classes = re.findall(r"`([^`]+)`", ticket)
    if args.cls:
        rule_class = args.cls
    elif ticket_classes and rule_class not in ticket_classes:
        print(f"CẢNH BÁO: changelog nói `{rule_class}` nhưng ticket nói {ticket_classes} -> kiểm tay", file=sys.stderr)

    # 2. class_id của lớp đó
    class_ids = set()
    for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            cid, name = ln.split(" ", 1)
            if name.strip() == rule_class:
                class_ids.add(int(cid))
    valid_ids = {int(ln.split(" ", 1)[0]) for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()}
    if not class_ids:
        raise SystemExit(f"Lớp `{rule_class}` không có trong classes.txt")

    # 3. job cũ theo jobs.csv
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    old_jobs = {j for j, r in jobs.items() if version_key(r["guideline"]) < version_key(change_ver)}

    # 4. ảnh, scene, job
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]
    scenes_all = {m["scene_id"] for m in meta}
    reported = sorted({s for s in scenes_all if re.search(rf"(?<![\w]){re.escape(s)}(?![\w])", ticket)})
    if not reported:
        print("CẢNH BÁO: ticket không nêu scene nào có trong metadata -> tier_a sẽ rỗng", file=sys.stderr)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    man = man.get("items", man)

    def has_class(stem: str) -> bool:
        item = man.get(stem, {})
        p = d / item["label"] if "label" in item else d / "labels" / f"{stem}.txt"
        if not p.is_file():
            return False
        for ln in p.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if not parts:
                continue
            try:
                cid = int(float(parts[0]))
            except ValueError:
                continue
            if cid in valid_ids and cid in class_ids:
                return True
        return False

    hit = [m for m in meta if m["job_id"] in old_jobs and has_class(m["image"])]
    tier_a = sorted(m["image"] for m in hit if m["scene_id"] in reported)
    tier_b = sorted(m["image"] for m in hit if m["scene_id"] not in reported)
    hit_jobs = sorted({m["job_id"] for m in hit})
    notify = sorted({jobs[j]["annotator"] for j in hit_jobs} | {jobs[j]["reviewer"] for j in hit_jobs})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"tier_a": tier_a, "tier_b": tier_b, "notify": notify}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print(f"Lớp đổi quy tắc : {rule_class} (class_id {sorted(class_ids)}), đổi ở {change_ver}")
    print(f"Job guideline cũ: {sorted(old_jobs)} (theo jobs.csv)")
    print(f"Scene ticket nêu: {reported}")
    print(f"tier_a ({len(tier_a)}): {tier_a}")
    print(f"tier_b ({len(tier_b)}): {tier_b}")
    print(f"Job liên quan   : {hit_jobs}")
    print(f"notify ({len(notify)}): {notify}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
