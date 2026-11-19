#!/usr/bin/env python3
"""
validator/validate.py - Bắt LỖI LUẬT trong một lô delivery (Day 10 Lab).

Cách chạy:
    python validator/validate.py <thu_muc_delivery> --out <errors.json>
           [--rules-out <rules.json>] [--candidates <candidates.json>]

Luồng chạy (đọc từ trên xuống dưới là hiểu cả chương trình):
    BƯỚC 1  load_context()                 nạp dữ liệu MỘT lần vào `ctx`
    BƯỚC 2  check_*()                      9 hàm, mỗi hàm bắt một loại lỗi
    BƯỚC 3  resolve_one_error_per_image()  mỗi ảnh giữ tối đa một lỗi
    BƯỚC 4  write_json()                   ghi errors.json (sắp xếp ổn định)

Ràng buộc: chỉ đọc thư mục delivery, chỉ thư viện chuẩn, không mạng.

!! CÁC GIẢ ĐỊNH VỀ TÊN KHOÁ JSON nằm hết ở mục "CẤU HÌNH TÊN KHOÁ" bên dưới.
   Chưa xem mẫu manifest.json / metadata.json / panoptic.json thật, nên mã dò
   nhiều tên khoá có thể có. Nếu chạy báo "không tìm thấy khoá", chỉ cần sửa
   các tuple đó, không phải sửa logic.
"""

import argparse
import csv
import hashlib
import json
import struct
import sys
import zlib
from collections import Counter, defaultdict
from itertools import accumulate
from pathlib import Path

# =====================================================================
# CẤU HÌNH DUNG SAI (chỉnh sau khi đo trên lô sạch runs/clean)
# =====================================================================
BBOX_EPSILON_NORMALIZED = 1e-5   # khử sai số làm tròn nhãn (6 chữ số thập phân). KHÔNG nới lớn.
DUP_SIZE_TOLERANCE_PX = 2.5      # duplicate_box: w, h hai box chênh tối đa chừng này pixel
DUP_CENTER_TOLERANCE_PX = 2.5    # duplicate_box: tâm hai box lệch tối đa chừng này pixel (mỗi trục)
DUP_FALLBACK_TOLERANCE_NORM = 0.01  # nếu không biết kích thước ảnh: dùng dung sai chuẩn hoá
AREA_TOLERANCE_PIXELS = 0        # thing_overlap: báo khi area_khai > pixel_thật + dung sai này
SKIP_CROWD_SEGMENTS = True       # bỏ segment iscrowd khỏi thing_overlap
ONLY_THING_CATEGORIES = True     # thing_overlap chỉ xét category isthing=1 (nếu có trường isthing)
HASH_FILE_KINDS = ("image",)     # thêm "label", "mask" để thử; kiểm báo thừa trên lô sạch

# Thứ tự ưu tiên khi MỘT ảnh dính nhiều luật (đứng trước thắng).
# Lý do: lỗi ở mức file làm các kiểm tra phía sau không còn ý nghĩa, rồi tới nhãn detection,
# metadata, cuối cùng là panoptic.
ERROR_PRIORITY = [
    "missing_image", "wrong_hash",
    "invalid_class", "bbox_out_of_bounds", "duplicate_box",
    "guideline_mismatch",
    "invalid_category_id", "thing_overlap",
]
# --- Ngưỡng đối chiếu detection <-> panoptic (chỉnh sau khi đo trên runs/clean) ---
CC_MIN_BOX_PIXELS = 4                # pixel segment trong box ít hơn thế này thì không xét ghép
CC_MIN_BBOX_IOU = 0.05               # cổng ghép: bbox box và bbox segment (tính từ mask) phải chạm nhau
CC_MIN_MATCH_SCORE = 0.10            # điểm ghép tối thiểu (thấp để box lệch nặng vẫn còn ghép được)
CC_MATCH_WEIGHT_PIXEL_IOU = 0.7      # điểm ghép = 0.7 * IoU pixel + 0.3 * IoU bbox
CC_MATCH_WEIGHT_BBOX_IOU = 0.3
CC_COVERAGE_MIN = 0.85               # bbox_drift: < 85% pixel của segment nằm trong box cùng lớp
CC_USE_BBOX_IOU_DRIFT = False        # bật để bắt box phình/co (coverage vẫn cao). DỄ báo thừa ở vật bị che: chỉ bật nếu lô sạch cho thấy ổn
CC_MAX_BBOX_IOU = 0.70               # ... khi IoU(box, bbox segment) < 0.70
CC_SWAP_MIN_COVERAGE = 0.60          # class/category_swap: segment nằm phần lớn trong box
CC_SWAP_MIN_FILL = 0.35              # ... và chiếm đáng kể diện tích box
CC_MERGE_MIN_FILL = 0.4              # instance_merge: mỗi box cùng lớp được segment đó lấp >= 40%
CC_MERGE_MAX_BOX_IOU = 0.5           # ... hai box khác nhau thật (loại duplicate_box)
CC_MERGE_MAX_COVERAGE = 0.9          # ... mỗi box chỉ chứa MỘT PHẦN segment (box chứa gần hết = box của chính nó)
CC_MERGE_MIN_COMBINED = 0.7          # ... và hai box cộng lại phủ >= 70% segment
CC_MISSING_MIN_AREA_FRACTION = 0.01  # missing_box: segment >= 1% diện tích ảnh, chưa được ghép với box nào
CC_MISSING_COVER_MIN = 0.5           # ... và không box nào chứa >= 50% pixel của nó
# Thứ tự ưu tiên khi MỘT ảnh có nhiều dấu hiệu: loại cụ thể nhất trước, missing_box (triệu chứng
# "còn sót") cuối cùng.
CC_TYPE_RANK = {"class_swap": 0, "instance_merge": 1, "bbox_drift": 2, "missing_box": 3}
SCENE_LEAK = "scene_leak"        # target là scene_id, xử lý riêng

# =====================================================================
# CẤU HÌNH TÊN KHOÁ (sửa ở đây nếu dữ liệu thật dùng tên khác)
# =====================================================================
RECORD_LIST_WRAPPER_KEYS = ("images", "files", "items", "records", "data")
IMAGE_NAME_KEYS = ("image", "image_id", "name", "file_name", "filename", "id", "stem")
SHA_KEYS = ("sha256", "hash", "sha")
PATH_KEYS = ("path", "file", "file_name", "filename", "rel_path")
SCENE_KEYS = ("scene_id", "scene")
SPLIT_KEYS = ("split",)
JOB_KEYS = ("job_id", "job")
GUIDELINE_KEYS = ("guideline_version", "guideline")
JOBS_CSV_JOB_COLUMN = "job_id"
JOBS_CSV_GUIDELINE_COLUMN = "guideline"


def normalize_name(name):
    """Chuẩn hoá tên lớp để ghép detection <-> panoptic qua TÊN."""
    return str(name).strip().lower().replace("_", " ")


def warn(message):
    """Cảnh báo ra stderr (stdout chỉ dành cho dòng tóm tắt cuối)."""
    print("[canh bao] " + message, file=sys.stderr)


# =====================================================================
# TIỆN ÍCH ĐỌC DỮ LIỆU
# =====================================================================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def first_present(mapping, keys, default=None):
    """Trả về giá trị của khoá đầu tiên có mặt trong mapping."""
    for k in keys:
        if isinstance(mapping, dict) and k in mapping and mapping[k] is not None:
            return mapping[k]
    return default


def stem_of(value):
    """'images/000000000139.jpg' -> '000000000139'. Chuỗi không có đuôi giữ nguyên."""
    return Path(str(value)).stem


def normalize_to_records(raw):
    """
    Đưa mọi dạng JSON về list các dict.
      - list các dict                -> giữ nguyên
      - dict có khoá bọc 'images'... -> lấy list bên trong
      - dict {tên_ảnh: {...}}        -> mỗi value thành dict, thêm '_key' = tên_ảnh
    """
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        for wrapper in RECORD_LIST_WRAPPER_KEYS:
            if isinstance(raw.get(wrapper), list):
                return [r for r in raw[wrapper] if isinstance(r, dict)]
            if isinstance(raw.get(wrapper), dict):
                return normalize_to_records(raw[wrapper])
        records = []
        for key, value in raw.items():
            if isinstance(value, dict):
                record = dict(value)
                record["_key"] = key
                records.append(record)
        return records
    return []


def record_image_stem(record):
    """Tên ảnh (không đuôi) của một bản ghi manifest/metadata."""
    if "_key" in record:
        return stem_of(record["_key"])
    name = first_present(record, IMAGE_NAME_KEYS)
    if isinstance(name, dict):                       # {"image": {"path": ...}}
        name = first_present(name, PATH_KEYS)
    return stem_of(name) if name is not None else None


def extract_path_and_sha(record, kind):
    """
    Lấy (đường_dẫn, sha256) của file loại `kind` ('image'|'label'|'mask') trong một bản ghi manifest.
    Thử các dạng thường gặp:
      A) {"image": {"path": "...", "sha256": "..."}}
      B) {"image": "images/x.jpg", "image_sha256": "..."}
      C) {"image": "images/x.jpg", "sha256": {"image": "..."}}
      D) {"files": {"image": {...}}}
    Không có thì trả (None, None).
    """
    holder = record.get("files", record) if isinstance(record.get("files"), dict) else record
    entry = holder.get(kind)
    path_value, sha_value = None, None
    if isinstance(entry, dict):                                   # dạng A / D
        path_value = first_present(entry, PATH_KEYS)
        sha_value = first_present(entry, SHA_KEYS)
    elif isinstance(entry, str):                                  # dạng B / C
        path_value = entry
    if path_value is None:
        path_value = first_present(holder, (kind + "_path", kind + "_file"))
    if sha_value is None:
        sha_value = first_present(holder, tuple(kind + "_" + k for k in SHA_KEYS))
    if sha_value is None and isinstance(holder.get("sha256"), dict):
        sha_value = holder["sha256"].get(kind)
    if sha_value is None and isinstance(holder.get("hashes"), dict):
        sha_value = holder["hashes"].get(kind)
    return path_value, (str(sha_value).strip().lower() if sha_value else None)


def sha256_of_file(path):
    """sha256 trên BYTES của file (mở 'rb')."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# =====================================================================
# ĐỌC MASK PNG (id segment = R + G*256 + B*256^2) - chỉ thư viện chuẩn
# =====================================================================
# Ghi chú: lab có sẵn scripts/pngutil.py. Chưa xem chữ ký hàm nên đây là bộ đọc độc lập.
# Nếu muốn dùng pngutil: viết lại DUY NHẤT hàm count_pixels_per_segment_id() cho trả về
# Counter {segment_id: số_pixel}. Các phần khác không phải sửa.
def read_png_dimensions(path):
    """Đọc chiều rộng/cao từ chunk IHDR (24 byte đầu)."""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("không phải PNG")
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_mask_id_rows(mask_path):
    """
    Trả về (rộng, cao, rows) với rows[y][x] = id segment của pixel. Giải mã PNG 8-bit RGB/RGBA, không interlace, rồi đếm số pixel cho từng id segment.
    Các bước:
      1) Đọc các chunk, gộp IDAT, zlib giải nén.
      2) Mỗi hàng có 1 byte 'filter' đứng đầu -> khôi phục (unfilter) về byte thô.
      3) Mỗi pixel (R,G,B) -> id = R + G*256 + B*65536, đếm bằng Counter.
    """
    data = Path(mask_path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("không phải PNG")
    position, idat, header = 8, bytearray(), None
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        position += 12 + length
    width, height, bit_depth, color_type, _, _, interlace = header
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise ValueError("chỉ hỗ trợ PNG 8-bit RGB/RGBA không interlace")
    bytes_per_pixel = 3 if color_type == 2 else 4
    stride = width * bytes_per_pixel
    raw = zlib.decompress(bytes(idat))

    rows = []
    previous_row = bytearray(stride)
    for row_index in range(height):
        start = row_index * (stride + 1)
        filter_type = raw[start]
        line = raw[start + 1:start + 1 + stride]
        if filter_type == 0:                                   # None
            row = bytearray(line)
        elif filter_type == 1:                                 # Sub: cộng byte bên trái
            row = bytearray(stride)
            for ch in range(bytes_per_pixel):
                row[ch::bytes_per_pixel] = bytes(
                    accumulate(line[ch::bytes_per_pixel], lambda x, y: (x + y) & 255))
        elif filter_type == 2:                                 # Up: cộng byte hàng trên
            row = bytearray((a + b) & 255 for a, b in zip(line, previous_row))
        elif filter_type in (3, 4):                            # Average / Paeth
            row = bytearray(stride)
            for i in range(stride):
                left = row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = previous_row[i]
                if filter_type == 3:
                    row[i] = (line[i] + ((left + up) >> 1)) & 255
                else:
                    up_left = previous_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                    row[i] = (line[i] + _paeth(left, up, up_left)) & 255
        else:
            raise ValueError("filter PNG không hợp lệ: %d" % filter_type)
        red = row[0::bytes_per_pixel]
        green = row[1::bytes_per_pixel]
        blue = row[2::bytes_per_pixel]
        rows.append([r + g * 256 + b * 65536 for r, g, b in zip(red, green, blue)])
        previous_row = row
    return width, height, rows


def count_pixels_per_segment_id(mask_path):
    """Số pixel của từng id segment trong mask (Counter {id: số_pixel})."""
    _, _, rows = decode_mask_id_rows(mask_path)
    counts = Counter()
    for row in rows:
        counts.update(row)
    return counts


def read_jpeg_dimensions(path):
    """Đọc (rộng, cao) JPEG bằng cách tìm marker SOF (không cần Pillow)."""
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("không tìm thấy SOF")


# =====================================================================
# BƯỚC 1 - NẠP DỮ LIỆU
# =====================================================================
class Context:
    """Gói toàn bộ dữ liệu đã nạp; các hàm check_* chỉ ĐỌC từ đây."""
    def __init__(self):
        self.root = None
        self.valid_class_ids = set()           # {0..79} lấy từ classes.txt
        self.manifest = {}                     # stem -> {"image": (path, sha), "label": ..., "mask": ...}
        self.metadata = {}                     # stem -> {"scene_id", "split", "job_id", "guideline"}
        self.job_guideline = {}                # job_id -> guideline của job
        self.panoptic_category_ids = set()     # category_id hợp lệ
        self.thing_category_ids = None         # None nếu file không có trường isthing
        self.segments = defaultdict(list)      # stem -> [segment dict]
        self.image_size = {}                   # stem -> (rộng, cao) pixel
        self.label_cache = {}                  # stem -> danh sách dòng nhãn đã parse
        self.class_name_by_id = {}             # id detection -> tên lớp (chuẩn hoá)
        self.category_name_by_id = {}          # category_id panoptic -> tên lớp (chuẩn hoá)


def load_context(root):
    ctx = Context()
    ctx.root = Path(root)

    # 1.1 classes.txt: mỗi dòng "class_id tên" (tên có thể có dấu cách -> split(None, 1))
    classes_path = ctx.root / "classes.txt"
    if classes_path.is_file():
        for line in classes_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split(None, 1)
            if parts and parts[0].lstrip("-").isdigit():
                ctx.valid_class_ids.add(int(parts[0]))
                if len(parts) > 1:
                    ctx.class_name_by_id[int(parts[0])] = normalize_name(parts[1])
    if not ctx.valid_class_ids:
        warn("classes.txt trống/không đọc được -> dùng mặc định 0..79")
        ctx.valid_class_ids = set(range(80))

    # 1.2 manifest.json: mỗi ảnh -> (đường dẫn, sha256) của image/label/mask
    for record in normalize_to_records(load_json(ctx.root / "manifest.json")):
        stem = record_image_stem(record)
        if stem is None:
            warn("bản ghi manifest không xác định được tên ảnh: %r" % list(record)[:6])
            continue
        ctx.manifest[stem] = {kind: extract_path_and_sha(record, kind)
                              for kind in ("image", "label", "mask")}
    if not ctx.manifest:
        raise SystemExit("manifest.json không đọc được bản ghi nào; kiểm tra IMAGE_NAME_KEYS/PATH_KEYS")

    # 1.3 metadata.json: scene_id, split, job_id, guideline_version
    metadata_path = ctx.root / "metadata.json"
    if metadata_path.is_file():
        for record in normalize_to_records(load_json(metadata_path)):
            stem = record_image_stem(record)
            if stem is None:
                continue
            ctx.metadata[stem] = {
                "scene_id": first_present(record, SCENE_KEYS),
                "split": first_present(record, SPLIT_KEYS),
                "job_id": first_present(record, JOB_KEYS),
                "guideline": first_present(record, GUIDELINE_KEYS),
            }

    # 1.4 jobs.csv: job_id -> guideline của job
    jobs_path = ctx.root / "jobs.csv"
    if jobs_path.is_file():
        with open(jobs_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                job = (row.get(JOBS_CSV_JOB_COLUMN) or "").strip()
                if job:
                    ctx.job_guideline[job] = (row.get(JOBS_CSV_GUIDELINE_COLUMN) or "").strip()

    # 1.5 panoptic.json: categories, kích thước ảnh, segments_info theo từng ảnh
    panoptic_path = ctx.root / "panoptic.json"
    if panoptic_path.is_file():
        panoptic = load_json(panoptic_path)
        thing_flags = {}
        for category in panoptic.get("categories", []):
            ctx.panoptic_category_ids.add(category["id"])
            ctx.category_name_by_id[category["id"]] = normalize_name(category.get("name", ""))
            if "isthing" in category:
                thing_flags[category["id"]] = bool(category["isthing"])
        if thing_flags:
            ctx.thing_category_ids = {cid for cid, flag in thing_flags.items() if flag}

        image_id_to_stem = {}
        for image in panoptic.get("images", []):
            stem = stem_of(image.get("file_name", image.get("id")))
            image_id_to_stem[image.get("id")] = stem
            if image.get("width") and image.get("height"):
                ctx.image_size[stem] = (image["width"], image["height"])
        for annotation in panoptic.get("annotations", []):
            if "file_name" in annotation:
                stem = stem_of(annotation["file_name"])
            else:
                stem = image_id_to_stem.get(annotation.get("image_id"))
            if stem is not None:
                ctx.segments[stem] = annotation.get("segments_info", [])
    return ctx


def resolve_path(ctx, stem, kind, default_dir, default_suffix):
    """Đường dẫn tuyệt đối của file: ưu tiên manifest, không có thì <thư mục>/<stem><đuôi>."""
    declared_path = ctx.manifest.get(stem, {}).get(kind, (None, None))[0]
    if declared_path:
        return ctx.root / declared_path
    return ctx.root / default_dir / (stem + default_suffix)


def get_image_size(ctx, stem):
    """Kích thước ảnh theo thứ tự: panoptic.json -> IHDR của mask -> SOF của JPEG; không có -> None."""
    if stem in ctx.image_size:
        return ctx.image_size[stem]
    for loader, path in ((read_png_dimensions, resolve_path(ctx, stem, "mask", "masks", ".png")),
                         (read_jpeg_dimensions, resolve_path(ctx, stem, "image", "images", ".jpg"))):
        try:
            ctx.image_size[stem] = loader(path)
            return ctx.image_size[stem]
        except Exception:
            continue
    return None


def get_label_rows(ctx, stem):
    """
    Parse nhãn YOLO của một ảnh (cache). Mỗi phần tử:
        {"class_raw": chuỗi, "class_id": int|None, "cx","cy","w","h": float}
    Dòng rỗng bị bỏ; dòng thiếu cột/không phải số bị bỏ kèm cảnh báo. File nhãn rỗng/thiếu -> [].
    """
    if stem in ctx.label_cache:
        return ctx.label_cache[stem]
    rows = []
    path = resolve_path(ctx, stem, "label", "labels", ".txt")
    if path.is_file():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            parts = line.split()
            if not parts:
                continue
            try:
                cx, cy, w, h = (float(x) for x in parts[1:5])
                if len(parts) < 5:
                    raise ValueError("thiếu cột")
            except ValueError:
                warn("%s dòng %d không đọc được: %r" % (path.name, line_number, line))
                continue
            try:
                class_id = int(parts[0])
            except ValueError:
                class_id = None                      # lớp không phải số nguyên -> invalid_class
            rows.append({"class_raw": parts[0], "class_id": class_id,
                         "cx": cx, "cy": cy, "w": w, "h": h})
    ctx.label_cache[stem] = rows
    return rows


# =====================================================================
# BƯỚC 2 - CÁC HÀM KIỂM TRA (mỗi hàm trả list {"type","target"})
# =====================================================================
def make_error(error_type, target):
    return {"type": error_type, "target": target}


def check_missing_image(ctx):
    """Luật: ảnh có trong manifest nhưng file ảnh không tồn tại. Target = tên ảnh."""
    found = []
    for stem in ctx.manifest:
        if not resolve_path(ctx, stem, "image", "images", ".jpg").is_file():
            found.append(make_error("missing_image", stem))
    return found


def check_wrong_hash(ctx):
    """
    Luật: sha256 TỰ TÍNH trên bytes khác sha256 ghi trong manifest (so chữ thường).
    File thiếu thì bỏ qua (đã là missing_image). Target = tên ảnh, kể cả khi hash lệch ở label/mask.
    """
    found = []
    for stem, entries in ctx.manifest.items():
        for kind in HASH_FILE_KINDS:
            declared_path, declared_sha = entries.get(kind, (None, None))
            if not declared_sha:
                continue
            file_path = resolve_path(ctx, stem, kind, kind + "s", {"image": ".jpg", "label": ".txt", "mask": ".png"}[kind])
            if not file_path.is_file():
                continue
            if sha256_of_file(file_path) != declared_sha:
                found.append(make_error("wrong_hash", stem))
                break
    return found


def check_invalid_class(ctx):
    """Luật: có dòng nhãn với class_id không nằm trong tập lớp hợp lệ (0-79) hoặc không phải số nguyên."""
    found = []
    for stem in ctx.manifest:
        for row in get_label_rows(ctx, stem):
            if row["class_id"] is None or row["class_id"] not in ctx.valid_class_ids:
                found.append(make_error("invalid_class", stem))
                break
    return found


def check_bbox_out_of_bounds(ctx):
    """
    Luật: box (cx,cy,w,h chuẩn hoá) có cạnh trái/phải/trên/dưới ngoài [0,1].
    Epsilon rất nhỏ chỉ để khử sai số làm tròn; tràn mép nhẹ vẫn bị báo.
    """
    eps = BBOX_EPSILON_NORMALIZED
    found = []
    for stem in ctx.manifest:
        for row in get_label_rows(ctx, stem):
            left, right = row["cx"] - row["w"] / 2, row["cx"] + row["w"] / 2
            top, bottom = row["cy"] - row["h"] / 2, row["cy"] + row["h"] / 2
            if left < -eps or top < -eps or right > 1 + eps or bottom > 1 + eps:
                found.append(make_error("bbox_out_of_bounds", stem))
                break
    return found


def check_duplicate_box(ctx):
    """
    Luật: hai box CÙNG lớp, CÙNG kích thước (chênh <= DUP_SIZE_TOLERANCE_PX),
    tâm lệch <= DUP_CENTER_TOLERANCE_PX theo cả hai trục. Không dùng IoU thấp vì COCO có cặp
    box tự nhiên chồng nhau nhưng khác kích thước.
    Không biết kích thước ảnh -> dùng dung sai chuẩn hoá DUP_FALLBACK_TOLERANCE_NORM.
    """
    found = []
    for stem in ctx.manifest:
        rows = [r for r in get_label_rows(ctx, stem) if r["class_id"] is not None]
        if len(rows) < 2:
            continue
        size = get_image_size(ctx, stem)
        if size:
            width_px, height_px = size
            size_tol_x, size_tol_y = DUP_SIZE_TOLERANCE_PX / width_px, DUP_SIZE_TOLERANCE_PX / height_px
            center_tol_x, center_tol_y = DUP_CENTER_TOLERANCE_PX / width_px, DUP_CENTER_TOLERANCE_PX / height_px
        else:
            size_tol_x = size_tol_y = center_tol_x = center_tol_y = DUP_FALLBACK_TOLERANCE_NORM
        is_duplicate = False
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if (a["class_id"] == b["class_id"]
                        and abs(a["w"] - b["w"]) <= size_tol_x and abs(a["h"] - b["h"]) <= size_tol_y
                        and abs(a["cx"] - b["cx"]) <= center_tol_x and abs(a["cy"] - b["cy"]) <= center_tol_y):
                    is_duplicate = True
                    break
            if is_duplicate:
                break
        if is_duplicate:
            found.append(make_error("duplicate_box", stem))
    return found


def check_scene_leak(ctx):
    """
    Luật: một scene_id có ảnh ở nhiều split (train và val). Target = scene_id (KHÔNG phải tên ảnh).
    """
    splits_of_scene = defaultdict(set)
    for entry in ctx.metadata.values():
        if entry["scene_id"] is not None and entry["split"] is not None:
            splits_of_scene[entry["scene_id"]].add(str(entry["split"]).strip().lower())
    return [make_error(SCENE_LEAK, str(scene)) for scene, splits in splits_of_scene.items() if len(splits) > 1]


def check_guideline_mismatch(ctx):
    """Luật: guideline ghi ở ảnh khác guideline của JOB (tra job_id trong jobs.csv). Không so ảnh với ảnh."""
    found = []
    for stem, entry in ctx.metadata.items():
        job_guideline = ctx.job_guideline.get(str(entry["job_id"]).strip()) if entry["job_id"] is not None else None
        image_guideline = str(entry["guideline"]).strip() if entry["guideline"] is not None else None
        if job_guideline and image_guideline and job_guideline != image_guideline:
            found.append(make_error("guideline_mismatch", stem))
    return found


def check_invalid_category_id(ctx):
    """Luật: segment có category_id không nằm trong `categories` của panoptic.json."""
    found = []
    for stem, segment_list in ctx.segments.items():
        if any(seg.get("category_id") not in ctx.panoptic_category_ids for seg in segment_list):
            found.append(make_error("invalid_category_id", stem))
    return found


def check_thing_overlap(ctx):
    """
    Luật (MỘT CHIỀU): `area` khai trong segments_info NHIỀU HƠN số pixel thật của segment trong mask
    (segment bị vật khác đè). Bỏ id 0 (nền), bỏ iscrowd (nếu bật), chỉ xét 'thing' (nếu biết).
    Mỗi mask được giải mã đúng một lần; ảnh không có segment cần xét thì không giải mã.
    """
    found = []
    for stem, segment_list in ctx.segments.items():
        candidates = []
        for seg in segment_list:
            if seg.get("id") in (0, None):
                continue
            if SKIP_CROWD_SEGMENTS and seg.get("iscrowd"):
                continue
            if ONLY_THING_CATEGORIES and ctx.thing_category_ids is not None \
                    and seg.get("category_id") not in ctx.thing_category_ids:
                continue
            candidates.append(seg)
        if not candidates:
            continue
        mask_path = resolve_path(ctx, stem, "mask", "masks", ".png")
        if not mask_path.is_file():
            warn("thiếu mask của %s (bỏ qua thing_overlap)" % stem)
            continue
        try:
            pixels_per_id = count_pixels_per_segment_id(mask_path)
        except Exception as exc:
            warn("không đọc được mask %s: %s" % (mask_path.name, exc))
            continue
        if any(seg.get("area", 0) > pixels_per_id.get(seg["id"], 0) + AREA_TOLERANCE_PIXELS for seg in candidates):
            found.append(make_error("thing_overlap", stem))
    return found


def yolo_to_pixel_box(row, width, height):
    """Box YOLO chuẩn hoá -> (x0, y0, x1, y1) pixel, cắt vào trong ảnh. Rỗng thì trả None."""
    x0 = max(0, int(round((row["cx"] - row["w"] / 2) * width)))
    y0 = max(0, int(round((row["cy"] - row["h"] / 2) * height)))
    x1 = min(width, int(round((row["cx"] + row["w"] / 2) * width)))
    y1 = min(height, int(round((row["cy"] + row["h"] / 2) * height)))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def box_iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def compute_segment_bboxes(rows, segment_ids):
    """Bbox pixel (x0, y0, x1, y1) của từng segment, tính từ CHÍNH mask (không tin bbox khai trong JSON)."""
    wanted = set(segment_ids)
    bboxes = {}
    for y, row in enumerate(rows):
        present = wanted.intersection(row)
        if not present:
            continue
        reversed_row = row[::-1]
        for seg_id in present:
            x_first = row.index(seg_id)
            x_last = len(row) - reversed_row.index(seg_id)
            old = bboxes.get(seg_id)
            if old is None:
                bboxes[seg_id] = [x_first, y, x_last, y + 1]
            else:
                old[0], old[2], old[3] = min(old[0], x_first), max(old[2], x_last), y + 1
    return bboxes


def pair_metrics(box, seg_bbox, inside_pixels, segment_total, box_area):
    """
    Bốn số đo độ khớp giữa một box detection và một segment panoptic:
      pixel_iou = inside / (box_area + segment_total - inside)  phạt CẢ HAI phía (segment tràn ra ngoài
                                                                 box lẫn box rộng hơn segment)
      coverage  = inside / segment_total   segment có nằm gọn trong box không
      fill      = inside / box_area        box có được segment lấp đầy không
      bbox_iou  = IoU(box, bbox của segment tính từ mask)
    """
    union = box_area + segment_total - inside_pixels
    return {"pixel_iou": inside_pixels / union if union else 0.0,
            "coverage": inside_pixels / segment_total if segment_total else 0.0,
            "fill": inside_pixels / box_area if box_area else 0.0,
            "bbox_iou": box_iou(box, seg_bbox) if seg_bbox else 0.0}


def crosscheck_one_image(ctx, stem):
    """
    Đối chiếu box detection với segment panoptic của MỘT ảnh. Quy trình:
      B1. Lọc segment: không crowd, và TÊN lớp phải là lớp detection có box (loại stuff như wall/sky).
      B2. instance_merge: một segment lấp >=40% của hai box cùng lớp khác nhau, MỖI box chỉ chứa một
          phần segment (<90%) và hai box cộng lại phủ >=70% segment -> tách riêng; hai box và segment đó
          không tham gia ghép cặp nữa. (Điều kiện "chỉ một phần" loại ca vật bị che: segment che lấp
          nhiều box nhưng đã có box riêng chứa trọn nó.)
      B3. GHÉP 1-1 box <-> segment: chấm điểm mọi cặp bằng IoU pixel (70%) + IoU bbox (30%), có cổng
          bbox_iou >= 0.05, rồi ghép tham lam từ điểm cao xuống; mỗi box và mỗi segment chỉ ghép một lần.
          (Không dùng 'segment nhiều pixel nhất trong box' vì vật bị che sẽ bị segment che nó cướp mất.)
      B4. Đánh giá từng cặp đã ghép:
            khác tên lớp + coverage>=0.6 + fill>=0.35 -> class_swap (hoặc category_swap, xem ảnh)
            cùng lớp + coverage<0.85                  -> bbox_drift
            cùng lớp + bbox_iou<0.70 (nếu bật)         -> bbox_drift (box phình/co)
      B5. missing_box: segment đủ lớn, CHƯA được ghép với box nào và không box nào chứa >=50% pixel.
      B6. Mỗi ảnh tối đa một lỗi: giữ ứng viên đứng đầu theo CC_TYPE_RANK, liệt kê phần còn lại ở
          trường 'alternatives' để người xem ảnh biết còn dấu hiệu nào khác.
    Segment crowd bị bỏ có chủ ý: COCO không có box detection cho vùng crowd nên đó là lệch TỰ NHIÊN.
    """
    mask_path = resolve_path(ctx, stem, "mask", "masks", ".png")
    if not mask_path.is_file():
        return []
    try:
        width, height, rows = decode_mask_id_rows(mask_path)
    except Exception as exc:
        warn("crosscheck bỏ qua %s: %s" % (stem, exc))
        return []

    # B1. segment hợp lệ để đối chiếu
    detection_class_names = set(ctx.class_name_by_id.values())
    segments = {}
    for seg in ctx.segments.get(stem, []):
        seg_id = seg.get("id")
        if seg_id in (0, None) or seg.get("iscrowd"):
            continue
        name = ctx.category_name_by_id.get(seg.get("category_id"), "")
        if name not in detection_class_names:
            continue
        if ctx.thing_category_ids is not None and seg.get("category_id") not in ctx.thing_category_ids:
            continue
        segments[seg_id] = name
    if not segments:
        return []
    total_pixels = Counter()
    for row in rows:
        total_pixels.update(row)
    seg_bbox = compute_segment_bboxes(rows, segments)

    # Box detection hợp lệ -> pixel, kèm số pixel của từng segment nằm trong box
    boxes = []
    for label_row in get_label_rows(ctx, stem):
        if label_row["class_id"] not in ctx.class_name_by_id:
            continue
        pixel_box = yolo_to_pixel_box(label_row, width, height)
        if pixel_box is None:
            continue
        inside = Counter()
        for y in range(pixel_box[1], pixel_box[3]):
            inside.update(rows[y][pixel_box[0]:pixel_box[2]])
        boxes.append({"box": pixel_box, "name": ctx.class_name_by_id[label_row["class_id"]],
                      "area": (pixel_box[2] - pixel_box[0]) * (pixel_box[3] - pixel_box[1]), "inside": inside})

    found = []

    def add(kind, score, seg_id, det_name, pan_name, box, reason, metrics=None):
        found.append({"type": kind, "score": score, "segment_id": seg_id, "det_class": det_name,
                      "pan_class": pan_name, "box": box, "reason": reason, "metrics": metrics})

    # B2. instance_merge
    merged_segments, merged_boxes = set(), set()
    for seg_id, seg_name in segments.items():
        same_class = [i for i, b in enumerate(boxes)
                      if b["name"] == seg_name
                      and b["inside"][seg_id] / b["area"] >= CC_MERGE_MIN_FILL
                      and b["inside"][seg_id] / total_pixels[seg_id] < CC_MERGE_MAX_COVERAGE]
        for x in range(len(same_class)):
            for y in range(x + 1, len(same_class)):
                i, j = same_class[x], same_class[y]
                combined = (boxes[i]["inside"][seg_id] + boxes[j]["inside"][seg_id]) / total_pixels[seg_id]
                if box_iou(boxes[i]["box"], boxes[j]["box"]) < CC_MERGE_MAX_BOX_IOU and combined >= CC_MERGE_MIN_COMBINED:
                    merged_segments.add(seg_id)
                    merged_boxes.update((i, j))
                    fill = min(boxes[i]["inside"][seg_id] / boxes[i]["area"],
                               boxes[j]["inside"][seg_id] / boxes[j]["area"])
                    add("instance_merge", fill, seg_id, seg_name, seg_name, boxes[i]["box"],
                        "một segment lấp >=%.0f%% của hai box cùng lớp" % (CC_MERGE_MIN_FILL * 100))
                    break
            if seg_id in merged_segments:
                break

    # B3. ghép 1-1 box <-> segment
    scored_pairs = []
    for box_index, b in enumerate(boxes):
        if box_index in merged_boxes:
            continue
        for seg_id in segments:
            inside_pixels = b["inside"][seg_id]
            if seg_id in merged_segments or inside_pixels < CC_MIN_BOX_PIXELS:
                continue
            metrics = pair_metrics(b["box"], seg_bbox.get(seg_id), inside_pixels, total_pixels[seg_id], b["area"])
            if metrics["bbox_iou"] < CC_MIN_BBOX_IOU:
                continue
            score = CC_MATCH_WEIGHT_PIXEL_IOU * metrics["pixel_iou"] + CC_MATCH_WEIGHT_BBOX_IOU * metrics["bbox_iou"]
            if score >= CC_MIN_MATCH_SCORE:
                scored_pairs.append((score, box_index, seg_id, metrics))
    scored_pairs.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_boxes, matched_segments, matches = set(), set(), []
    for score, box_index, seg_id, metrics in scored_pairs:
        if box_index in used_boxes or seg_id in matched_segments:
            continue
        used_boxes.add(box_index)
        matched_segments.add(seg_id)
        matches.append((box_index, seg_id, metrics))

    # B4. đánh giá từng cặp
    for box_index, seg_id, m in matches:
        b = boxes[box_index]
        if b["name"] != segments[seg_id]:
            if m["coverage"] >= CC_SWAP_MIN_COVERAGE and m["fill"] >= CC_SWAP_MIN_FILL:
                add("class_swap", min(m["coverage"], m["fill"]), seg_id, b["name"], segments[seg_id], b["box"],
                    "box khớp segment nhưng khác lớp (class_swap hoặc category_swap, xem ảnh)", m)
        elif m["coverage"] < CC_COVERAGE_MIN:
            add("bbox_drift", 1 - m["coverage"], seg_id, b["name"], segments[seg_id], b["box"],
                "chỉ %.0f%% pixel segment nằm trong box" % (m["coverage"] * 100), m)
        elif CC_USE_BBOX_IOU_DRIFT and m["bbox_iou"] < CC_MAX_BBOX_IOU:
            add("bbox_drift", 1 - m["bbox_iou"], seg_id, b["name"], segments[seg_id], b["box"],
                "IoU(box, bbox segment) chỉ %.2f dù segment nằm trong box" % m["bbox_iou"], m)

    # B5. missing_box
    image_area = width * height
    for seg_id, seg_name in segments.items():
        if seg_id in matched_segments or seg_id in merged_segments:
            continue
        if total_pixels[seg_id] < CC_MISSING_MIN_AREA_FRACTION * image_area:
            continue
        if any(b["inside"][seg_id] / total_pixels[seg_id] >= CC_MISSING_COVER_MIN for b in boxes):
            continue
        add("missing_box", total_pixels[seg_id] / image_area, seg_id, None, seg_name, None,
            "segment %.1f%% diện tích ảnh chưa có box nào" % (100 * total_pixels[seg_id] / image_area))

    # B6. một ảnh một ứng viên
    if not found:
        return []
    found.sort(key=lambda c: (CC_TYPE_RANK[c["type"]], -c["score"]))
    top, rest = found[0], found[1:]
    return [{"image": stem, "type": top["type"], "det_class": top["det_class"], "pan_class": top["pan_class"],
             "box_px": list(top["box"]) if top["box"] else None, "segment_id": top["segment_id"],
             "segment_bbox_px": seg_bbox.get(top["segment_id"]), "score": round(top["score"], 3),
             "reason": top["reason"],
             "match": {k: round(v, 3) for k, v in top["metrics"].items()} if top["metrics"] else None,
             "alternatives": [{"type": c["type"], "segment_id": c["segment_id"], "score": round(c["score"], 3)}
                              for c in rest]}]


def build_candidates(ctx, skip_images=()):
    """
    Ứng viên lỗi gán nhãn để NGƯỜI XEM ẢNH quyết định. Bỏ qua ảnh đã dính lỗi luật (mỗi ảnh một lỗi).
    Sắp xếp theo điểm giảm dần để xem ca đáng ngờ nhất trước.
    """
    skip = set(skip_images)
    candidates = []
    for stem in sorted(ctx.manifest):
        if stem in skip:
            continue
        try:
            candidates.extend(crosscheck_one_image(ctx, stem))
        except Exception as exc:
            warn("crosscheck lỗi ở %s: %r" % (stem, exc))
    return sorted(candidates, key=lambda c: (-c["score"], c["image"]))


def write_review_template(path, candidates):
    """Mẫu review_log.csv: để trống verdict/note, người xem ảnh điền (confirmed|rejected + thấy gì)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "type", "verdict", "note"])
        for c in candidates:
            writer.writerow([c["image"], c["type"], "", ""])


# =====================================================================
# BƯỚC 3 - MỖI ẢNH TỐI ĐA MỘT LỖI
# =====================================================================
def resolve_one_error_per_image(all_errors):
    """
    Ground truth chỉ có tối đa một lỗi/ảnh, nên ảnh dính >=2 luật thì ít nhất một luật là báo thừa.
    Giữ luật có ưu tiên cao nhất (ERROR_PRIORITY), cảnh báo các luật bị loại.
    scene_leak (target = scene_id) giữ nguyên, không đụng quy tắc này.
    """
    priority_of = {name: rank for rank, name in enumerate(ERROR_PRIORITY)}
    by_image = defaultdict(list)
    kept = []
    for error in all_errors:
        if error["type"] == SCENE_LEAK:
            kept.append(error)
        else:
            by_image[error["target"]].append(error["type"])
    for image, types in by_image.items():
        types = sorted(set(types), key=lambda t: priority_of.get(t, 999))
        if len(types) > 1:
            warn("ảnh %s dính nhiều luật %s -> giữ %s" % (image, types, types[0]))
        kept.append(make_error(types[0], image))
    return kept


# =====================================================================
# BƯỚC 4 - GHI KẾT QUẢ
# =====================================================================
def write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Validator lỗi luật cho lô delivery")
    parser.add_argument("delivery", help="thư mục delivery")
    parser.add_argument("--out", required=True, help="errors.json")
    parser.add_argument("--rules-out", help="rules.json (lỗi luật, cùng schema)")
    parser.add_argument("--candidates", help="candidates.json (đối chiếu det<->panoptic)")
    parser.add_argument("--review-template", help="review_log.csv mẫu (cần --candidates)")
    args = parser.parse_args()

    if not Path(args.delivery).is_dir():
        print("không đọc được thư mục: %s" % args.delivery, file=sys.stderr)
        return 2

    ctx = load_context(args.delivery)                                        # BƯỚC 1
    checks = (check_missing_image, check_wrong_hash, check_invalid_class,    # BƯỚC 2
              check_bbox_out_of_bounds, check_duplicate_box, check_scene_leak,
              check_guideline_mismatch, check_invalid_category_id, check_thing_overlap)
    all_errors = []
    for check in checks:
        try:
            all_errors.extend(check(ctx))
        except Exception as exc:                  # một luật hỏng không được làm sập cả chương trình
            warn("%s bị lỗi: %r" % (check.__name__, exc))
    final_errors = sorted(resolve_one_error_per_image(all_errors),           # BƯỚC 3
                          key=lambda e: (e["type"], e["target"]))

    write_json(args.out, {"errors": final_errors})                           # BƯỚC 4
    if args.rules_out:
        write_json(args.rules_out, {"errors": final_errors})
    if args.candidates:
        already_flagged = {e["target"] for e in final_errors if e["type"] != SCENE_LEAK}
        candidates = build_candidates(ctx, already_flagged)
        write_json(args.candidates, {"candidates": candidates})
        if args.review_template:
            write_review_template(args.review_template, candidates)
        by_kind = Counter(c["type"] for c in candidates)
        print("[ung vien] %d: %s" % (len(candidates), dict(by_kind)), file=sys.stderr)

    summary = Counter(e["type"] for e in final_errors)
    print("tong %d loi: %s" % (len(final_errors), ", ".join("%s=%d" % kv for kv in sorted(summary.items())) or "khong co"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
