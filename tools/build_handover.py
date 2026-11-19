#!/usr/bin/env python3
"""Build a detection v2 handover from a run's delivery and reviewed errors.

Wrong-hash images must be opened and visually checked by a person first:
  python tools/build_handover.py --run runs/r83 \
      --wrong-hash-good 000000000139 \
      --wrong-hash-corrupt 000000000140
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


DETECTION_REWORK = {
    "missing_image",
    "invalid_class",
    "bbox_out_of_bounds",
    "duplicate_box",
    "class_swap",
    "bbox_drift",
    "missing_box",
}
PANOPTIC_ERRORS = {
    "invalid_category_id",
    "thing_overlap",
    "category_swap",
    "instance_merge",
}
SUPPORTED_ERRORS = DETECTION_REWORK | PANOPTIC_ERRORS | {
    "wrong_hash",
    "guideline_mismatch",
    "scene_leak",
}
THRESHOLD = 0.02


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Không đọc được JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path} phải chứa một object JSON")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise SystemExit(f"Không đọc được CSV {path}: {exc}") from exc


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def delivery_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise SystemExit(f"Đường dẫn manifest không hợp lệ: {relative!r}")
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise SystemExit(f"Từ chối đường dẫn ra ngoài delivery/: {relative}")
    return path


def read_errors(path: Path, items: dict, metadata: dict) -> list[dict[str, str]]:
    document = read_json(path)
    rows = document.get("errors")
    if not isinstance(rows, list):
        raise SystemExit(f"{path} cần khóa 'errors' là một danh sách")

    scenes = {row["scene_id"] for row in metadata.values()}
    found = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("Mỗi lỗi trong errors.json phải là object")
        kind, target = row.get("type"), row.get("target")
        if not isinstance(kind, str) or kind not in SUPPORTED_ERRORS:
            raise SystemExit(f"Loại lỗi không được hỗ trợ: {kind!r}")
        if not isinstance(target, str) or not target:
            raise SystemExit(f"Target không hợp lệ cho lỗi {kind}")
        if kind == "scene_leak":
            if target not in scenes:
                raise SystemExit(f"scene_leak không có scene_id trong metadata: {target}")
        elif target not in items:
            raise SystemExit(f"Lỗi {kind} trỏ tới ảnh không có trong manifest: {target}")
        found.add((kind, target))
    return [{"type": kind, "target": target} for kind, target in sorted(found)]


def load_classes(path: Path) -> list[str]:
    classes: dict[int, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise SystemExit(f"{path}:{number}: cần định dạng 'class_id tên'")
        try:
            class_id = int(parts[0])
        except ValueError as exc:
            raise SystemExit(f"{path}:{number}: class_id không hợp lệ") from exc
        if class_id in classes:
            raise SystemExit(f"{path}:{number}: class_id {class_id} bị lặp")
        classes[class_id] = parts[1].strip()
    if sorted(classes) != list(range(80)):
        raise SystemExit(f"{path} phải khai báo đủ class_id 0..79")
    return [classes[index] for index in range(80)]


def label_count(path: Path, class_names: list[str]) -> Counter:
    counts: Counter = Counter()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise SystemExit(f"{path}:{number}: nhãn YOLO cần đúng 5 trường")
        try:
            class_value = float(fields[0])
            class_id = int(class_value)
        except ValueError as exc:
            raise SystemExit(f"{path}:{number}: class_id không hợp lệ") from exc
        if class_value != class_id or not 0 <= class_id < len(class_names):
            raise SystemExit(f"{path}:{number}: class_id ngoài 0..79: {fields[0]}")
        counts[class_names[class_id]] += 1
    return counts


def scene_split_choices(metadata: dict, errors: list[dict[str, str]]) -> dict[str, str]:
    leaked = {row["target"] for row in errors if row["type"] == "scene_leak"}
    members: dict[str, Counter] = defaultdict(Counter)
    for row in metadata.values():
        members[row["scene_id"]][row["split"]] += 1

    choices = {}
    for scene in leaked:
        counts = members[scene]
        top_count = max(counts.values())
        winners = {split for split, count in counts.items() if count == top_count}
        choices[scene] = "train" if "train" in winners else sorted(winners)[0]
    return choices


def verify_v1(delivery: Path, manifest: dict, metadata_path: Path, release: dict) -> None:
    expected_id = "lab250_" + hashlib.sha256(
        (delivery / "manifest.json").read_bytes() + metadata_path.read_bytes()
    ).hexdigest()[:12]
    if release.get("release_id") != expected_id:
        raise SystemExit("release_id không khớp manifest/metadata; không sửa v1, hãy báo nhóm")

    for name, item in manifest.items():
        for field in ("label", "mask"):
            path = delivery_path(delivery, item.get(field))
            if not path.is_file():
                raise SystemExit(f"Thiếu {field} của {name}; không thể xác nhận v1 nguyên vẹn")
            expected_hash = item.get(f"{field}_sha256")
            if not isinstance(expected_hash, str) or sha256(path) != expected_hash:
                raise SystemExit(f"{field} của {name} khác manifest v1; không sửa v1")


def write_readme(
    path: Path,
    release_id: str,
    parent: str,
    image_count: int,
    label_total: int,
    v1_errors: int,
    original_count: int,
    v1_decision: str,
    guideline_summary: str,
    notes: str,
) -> None:
    rate = v1_errors / original_count if original_count else 0
    text = (
        f"Release: {release_id}_v2\n"
        f"Parent: {parent}\n"
        f"Số ảnh: {image_count}\n"
        f"Số nhãn: {label_total}\n"
        f"Guideline: {guideline_summary}\n"
        f"QC v1: {v1_errors}/{original_count} = {rate:.1%}\n"
        f"Kết luận v1: {v1_decision} — "
        f"{'tỉ lệ lỗi vượt ngưỡng 2%' if rate > THRESHOLD else 'tỉ lệ lỗi không vượt ngưỡng 2%'}\n"
        "Kết luận v2: Release — lỗi detection cần gán lại đã được tách khỏi lô; "
        "các sửa đổi metadata/hash được ghi trong Ghi chú\n"
        f"Ghi chú: {notes}\n"
    )
    path.write_text(text, encoding="utf-8")


def replace_output(staging: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.previous")
    if destination.is_symlink() or backup.exists():
        raise SystemExit(f"Từ chối thay thế đường dẫn không an toàn: {destination}")
    moved_old = False
    if destination.exists():
        if not destination.is_dir():
            raise SystemExit(f"Đích đã tồn tại nhưng không phải thư mục: {destination}")
        os.replace(destination, backup)
        moved_old = True
    try:
        os.replace(staging, destination)
    except OSError:
        if moved_old:
            os.replace(backup, destination)
        raise
    if moved_old:
        shutil.rmtree(backup)


def build(run: Path, wrong_hash_good: set[str], wrong_hash_corrupt: set[str]) -> Path:
    delivery = run / "delivery"
    if not delivery.is_dir():
        raise SystemExit(f"Không tìm thấy delivery/: {delivery}")
    manifest_doc = read_json(delivery / "manifest.json")
    items = manifest_doc.get("items")
    if not isinstance(items, dict) or not items:
        raise SystemExit("manifest.json cần có danh sách items không rỗng")
    manifest = {str(name): item for name, item in items.items()}
    if any(not isinstance(item, dict) for item in manifest.values()):
        raise SystemExit("Mỗi item trong manifest.json phải là object")
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", name) for name in manifest):
        raise SystemExit("Tên ảnh trong manifest chứa ký tự không hợp lệ")

    metadata_rows = read_json(delivery / "metadata.json").get("items")
    if not isinstance(metadata_rows, list):
        raise SystemExit("metadata.json cần có danh sách items")
    metadata = {row["image"]: row for row in metadata_rows if isinstance(row, dict) and "image" in row}
    if len(metadata) != len(metadata_rows) or set(metadata) != set(manifest):
        raise SystemExit("metadata.json và manifest.json không có cùng tập ảnh")
    job_rows = read_csv(delivery / "jobs.csv")
    jobs = {row.get("job_id"): row for row in job_rows}
    if None in jobs or len(jobs) == 0 or len(jobs) != len(job_rows):
        raise SystemExit("jobs.csv thiếu job_id hoặc không có dữ liệu")
    for name, row in metadata.items():
        if row.get("job_id") not in jobs:
            raise SystemExit(f"Ảnh {name} trỏ tới job không có trong jobs.csv")

    release = read_json(delivery / "release.json")
    release_id = release.get("release_id")
    if not isinstance(release_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", release_id):
        raise SystemExit("release.json thiếu release_id hợp lệ")
    verify_v1(delivery, manifest, delivery / "metadata.json", release)
    errors = read_errors(run / "errors.json", manifest, metadata)

    hash_targets = set()
    for row in errors:
        if row["type"] == "wrong_hash":
            image_path = delivery_path(delivery, manifest[row["target"]].get("image"))
            if image_path.is_file():
                hash_targets.add(row["target"])
    if wrong_hash_good & wrong_hash_corrupt:
        raise SystemExit("--wrong-hash-good và --wrong-hash-corrupt không được trùng ảnh")
    if (wrong_hash_good | wrong_hash_corrupt) - hash_targets:
        raise SystemExit("Có ảnh trong cờ wrong-hash không nằm trong errors.json hoặc ảnh bị thiếu")
    unreviewed_hashes = hash_targets - wrong_hash_good - wrong_hash_corrupt
    if unreviewed_hashes:
        raise SystemExit(
            "Mở và kiểm ảnh wrong_hash bằng mắt, rồi chỉ rõ mỗi ảnh bằng "
            "--wrong-hash-good hoặc --wrong-hash-corrupt: "
            + ", ".join(sorted(unreviewed_hashes))
        )

    error_by_image: dict[str, set[str]] = defaultdict(set)
    for row in errors:
        if row["type"] != "scene_leak":
            error_by_image[row["target"]].add(row["type"])
    scene_choices = scene_split_choices(metadata, errors)
    class_names = load_classes(delivery / "classes.txt")

    rework_names = {
        name for name, kinds in error_by_image.items()
        if kinds & DETECTION_REWORK or name in wrong_hash_corrupt
    }
    for name, item in manifest.items():
        image_path = delivery_path(delivery, item.get("image"))
        label_path = delivery_path(delivery, item.get("label"))
        mask_path = delivery_path(delivery, item.get("mask"))
        if not image_path.is_file() and name not in rework_names:
            raise SystemExit(f"Thiếu ảnh {name} nhưng errors.json không có missing_image")
        if not label_path.is_file():
            raise SystemExit(f"Thiếu nhãn của {name}; không có loại lỗi để bàn giao an toàn")
        if not mask_path.is_file():
            raise SystemExit(f"Thiếu mask của {name}; không thể xác nhận v1 nguyên vẹn")

    for name, kinds in error_by_image.items():
        image_path = delivery_path(delivery, manifest[name]["image"])
        if "wrong_hash" in kinds and image_path.is_file():
            stored_hash = manifest[name].get("image_sha256")
            if not isinstance(stored_hash, str) or sha256(image_path) == stored_hash:
                raise SystemExit(f"wrong_hash của {name} không khớp dữ liệu trong manifest")

    for row in errors:
        if row["type"] == "scene_leak":
            scene_members = [m for m in metadata.values() if m["scene_id"] == row["target"]]
            if len({m["split"] for m in scene_members}) < 2:
                raise SystemExit(f"scene_leak của {row['target']} không khớp metadata hiện tại")
        elif row["type"] == "guideline_mismatch":
            meta = metadata[row["target"]]
            if meta.get("guideline_version") == jobs[meta["job_id"]].get("guideline"):
                raise SystemExit(f"guideline_mismatch của {row['target']} không khớp dữ liệu hiện tại")

    handover_root = run / "handover"
    handover_root.mkdir(parents=True, exist_ok=True)
    destination = handover_root / f"{release_id}_v2"
    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}_v2.", dir=handover_root))
    (staging / "images").mkdir()
    (staging / "labels").mkdir()
    try:
        kept_names = []
        rework_rows = []
        for name in sorted(manifest):
            meta = metadata[name]
            kinds = sorted(error_by_image.get(name, set()))
            if name in rework_names:
                job = jobs[meta["job_id"]]
                all_kinds = sorted(set(kinds) | ({"wrong_hash"} if name in wrong_hash_corrupt else set()))
                rework_rows.append({
                    "image": name,
                    "type": ";".join(all_kinds),
                    "annotator": job.get("annotator", ""),
                    "reviewer": job.get("reviewer", ""),
                    "action": "Gán lại nhãn detection; kiểm tra ảnh và nhãn trước khi nhận lại",
                })
                continue

            item = manifest[name]
            image_path = delivery_path(delivery, item["image"])
            label_path = delivery_path(delivery, item["label"])
            if image_path.stem != name or label_path.stem != name:
                raise SystemExit(f"Tên file image/label không khớp target {name}")
            shutil.copyfile(image_path, staging / "images" / f"{name}{image_path.suffix}")
            shutil.copyfile(label_path, staging / "labels" / f"{name}{label_path.suffix}")
            kept_names.append(name)

        hash_rows = []
        label_counts: Counter = Counter()
        for subdir in ("images", "labels"):
            for path in sorted((staging / subdir).iterdir()):
                hash_rows.append({
                    "file": f"{subdir}/{path.name}",
                    "sha256": sha256(path),
                })
        for name in kept_names:
            label_counts.update(label_count(staging / "labels" / f"{name}.txt", class_names))
        write_csv(staging / "manifest.csv", ["file", "sha256"], hash_rows)

        summary_rows = [
            {"class": class_name, "count": label_counts[class_name]}
            for class_name in class_names
            if label_counts[class_name]
        ]
        summary_rows.append({"class": "TOTAL", "count": sum(label_counts.values())})
        write_csv(staging / "label_summary.csv", ["class", "count"], summary_rows)
        write_csv(
            staging / "rework_queue.csv",
            ["image", "type", "annotator", "reviewer", "action"],
            rework_rows,
        )

        trace_rows = []
        guideline_jobs: dict[str, set[str]] = defaultdict(set)
        for name in kept_names:
            meta = metadata[name]
            job = jobs[meta["job_id"]]
            split = scene_choices.get(meta["scene_id"], meta["split"])
            trace_rows.append({
                "image": name,
                "scene_id": meta["scene_id"],
                "split": split,
                "job_id": meta["job_id"],
                "annotator": job.get("annotator", ""),
                "reviewer": job.get("reviewer", ""),
                "guideline": job.get("guideline", ""),
            })
            guideline_jobs[job.get("guideline", "")].add(meta["job_id"])
        write_csv(
            staging / "truyvet.csv",
            ["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"],
            trace_rows,
        )

        original_count = len(manifest)
        v1_error_count = len({row["target"] for row in errors})
        v1_rate = v1_error_count / original_count
        v1_decision = "Hold" if v1_rate > THRESHOLD else "Release"
        guideline_summary = "; ".join(
            f"{guideline} ({', '.join(sorted(job_ids))})"
            for guideline, job_ids in sorted(guideline_jobs.items())
        ) or "không có ảnh"

        note_parts = []
        if wrong_hash_good:
            note_parts.append(
                "Ảnh wrong_hash đã được mở kiểm tra, còn nguyên; manifest v2 ghi SHA-256 mới cho "
                + ", ".join(sorted(wrong_hash_good))
            )
        if wrong_hash_corrupt:
            note_parts.append(
                "Ảnh wrong_hash hỏng được chuyển rework: " + ", ".join(sorted(wrong_hash_corrupt))
            )
        if scene_choices:
            note_parts.append(
                "Đã đưa các cảnh rò split về một split: "
                + ", ".join(f"{scene} → {split}" for scene, split in sorted(scene_choices.items()))
            )
        if any(row["type"] == "guideline_mismatch" for row in errors):
            note_parts.append("truyvet.csv lấy guideline theo jobs.csv")
        pano_names = sorted({
            row["target"] for row in errors if row["type"] in PANOPTIC_ERRORS
        })
        if pano_names:
            note_parts.append(
                "Lỗi panoptic giữ nguyên ảnh detection; báo team panoptic cho ảnh "
                + ", ".join(pano_names)
            )
        if rework_rows:
            note_parts.append(f"{len(rework_rows)} ảnh được giao lại theo jobs.csv")
        notes = "; ".join(note_parts) or "Không có lỗi cần sửa hoặc chuyển rework."
        write_readme(
            staging / "README.txt",
            release_id,
            release_id,
            len(kept_names),
            sum(label_counts.values()),
            v1_error_count,
            original_count,
            v1_decision,
            guideline_summary,
            notes,
        )
        replace_output(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    print(f"Đã tạo {destination}")
    print(f"Ảnh giữ lại: {len(kept_names)}; ảnh rework: {len(rework_rows)}")
    print("Bước tiếp theo: chạy scripts/pack_release.py rồi scripts/check_handover.py.")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo lô bàn giao v2 từ delivery và errors.json")
    parser.add_argument("--run", required=True, help="thư mục runs/r<seed>")
    parser.add_argument(
        "--wrong-hash-good",
        action="append",
        default=[],
        metavar="IMAGE",
        help="ảnh wrong_hash đã mở kiểm và còn nguyên; có thể lặp lại",
    )
    parser.add_argument(
        "--wrong-hash-corrupt",
        action="append",
        default=[],
        metavar="IMAGE",
        help="ảnh wrong_hash đã mở kiểm và bị hỏng, cần rework; có thể lặp lại",
    )
    args = parser.parse_args()
    build(
        Path(args.run).resolve(),
        set(args.wrong_hash_good),
        set(args.wrong_hash_corrupt),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
