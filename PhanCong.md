# Phân công nhóm 83 — Day 10 Lab

> Phân công theo **người chịu trách nhiệm**, không theo pha: mỗi người sở hữu trọn một mảng từ lúc viết code tới lúc nộp, kể cả phần việc trong đề ẩn.
> Bảng thành viên chính thức để nộp vẫn là [submission/TEAM.md](submission/TEAM.md) (cần thêm họ tên, MSHV).

| Vai | GitHub | Họ tên | Mảng sở hữu |
|---|---|---|---|
| Người 1 | baodu1204 | | Validator luật |
| Người 2 | Hung-1812 | Trần Thành Hùng | Đối chiếu detection ↔ panoptic |
| Người 3 — **Lead** | nguyenloc2004 | | Điều phối nhóm; công cụ xem ảnh, gộp review, quyết định, truy vết |
| Người 4 | zenlylove | | Bàn giao v2, bảo mật, nộp bài |

**Lead (nguyenloc2004)** ngoài mảng của Người 3 còn: chốt format dùng chung (cuối file), chia hàng đợi xem ảnh, review và merge code của mọi người vào `main`, theo dõi mốc trong [CHECKPOINTS.md](CHECKPOINTS.md), tổ chức buổi diễn tập đề ẩn, và quyết định cuối khi nhóm bất đồng (ví dụ một ca `confirmed` hay `rejected`).

Seed luyện tập: `83` · Seed thử thêm: `11`, `22` · Lô sạch: `runs/clean`

---

## Người 1 (baodu1204) — Validator luật

**Sở hữu:** `validator/validate.py` (khung chương trình + toàn bộ lỗi luật), `submission/prompts.md`.

Việc phải làm:
1. Viết khung `validate.py` đúng giao diện cố định: `validate.py <delivery> --out <file> [--candidates <file>]`. Hàm nạp dữ liệu dùng chung: manifest, metadata, jobs, classes, panoptic, labels đã parse, mask đếm pixel (qua `scripts/pngutil.py`).
2. Viết 9 kiểm luật: `missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`, `scene_leak`, `guideline_mismatch`, `invalid_category_id`, `thing_overlap`.
3. Quy tắc mỗi ảnh tối đa một lỗi (thứ tự ưu tiên khi một ảnh dính nhiều luật).
4. Tự kiểm: lỗi luật F1 ≈ 1.0 trên seed `83`, `11`, `22`; lô sạch không báo lỗi luật nào. Ghi số F1 thật cho Người 2 đưa vào REPORT.
5. Bảo đảm luật cấm: chỉ đọc `delivery/`, chỉ thư viện chuẩn, không mạng, không hard-code tên ảnh.
6. Gom và ghi `prompts.md`: mọi lần cả nhóm dùng AI (ai, prompt, AI sai ở đâu, kiểm lại thế nào). Nhắc mọi người gửi prompt của mình.

**Trong đề ẩn:** giải nén `de_an.zip`, chạy validator ngay phút đầu, gửi danh sách ứng viên cho cả nhóm; sau đó xem ảnh phần hàng đợi của mình.

---

## Người 2 (Hung-1812 · Trần Thành Hùng) — Đối chiếu detection ↔ panoptic

**Sở hữu:** phần cross-check trong `validate.py` (hàm sinh `candidates.json`), ngưỡng lọc ứng viên, REPORT mục 1–2.

Việc phải làm:
1. Ghép box YOLO (đổi sang pixel) với segment thing non-crowd, ghép lớp qua **tên** (`classes.txt` ↔ `categories`), dùng tỉ lệ pixel mask nằm trong box thay vì chỉ IoU bbox.
2. Sinh ứng viên cho `class_swap` / `category_swap`, `bbox_drift`, `missing_box`, `instance_merge`, ghi vào `candidates.json` theo format chung (cuối file).
3. Đo nhiễu tự nhiên trên `runs/clean`; chỉnh ngưỡng để hàng đợi đủ nhỏ cho 4 người xem hết trong khoảng 25 phút mà không bỏ sót lỗi. Không dùng `_private` để chọn ngưỡng.
4. Thử trên nhiều seed để chắc ngưỡng không chỉ hợp với seed `83` (đề ẩn có mức lỗi khác, ảnh bị lật / nén lại).
5. Viết `submission/REPORT.md` mục 1 (F1 theo seed, số ứng viên lô sạch, ngưỡng và cách chọn) và mục 2 (vì sao báo hết ứng viên làm F1 giảm, dùng số thật).

**Trong đề ẩn:** canh số lượng ứng viên; nếu hàng đợi quá dài thì quyết định thứ tự ưu tiên xem; xem ảnh phần hàng đợi của mình.

---

## Người 3 (nguyenloc2004 · Lead) — Công cụ xem ảnh, gộp review, quyết định, truy vết

**Sở hữu:** `tools/view.py` (công cụ xem ảnh, được dùng Pillow), `tools/trace_query.py`, `review_log.csv` (gộp), `errors.json` cuối, lineage HOLD, `trace.json`, REPORT mục 3 và 5.

Việc phải làm:
1. Viết `tools/view.py`: mở một ảnh theo tên, vẽ box detection (kèm tên lớp) và viền segment panoptic (kèm tên lớp), phóng to vùng quanh vật. Phải chạy nhanh vì đề ẩn chỉ có 40 phút.
2. Chuẩn bị mẫu `review_log.csv` (`image,type,verdict,note`), chia hàng đợi ứng viên cho 4 người, gộp các dòng của mọi người thành một file; kiểm note ≥ 20 ký tự, nói rõ thấy gì, không chép giống nhau, có tên người xem.
3. Chạy `scripts/merge_review.py` ra `errors.json` cuối; chạy `score_findings.py` tự đo.
4. Tính QC v1, ghi lineage: `lineage.py record --event decision ... --decision HOLD`, chạy `lineage.py impact` (mong đợi `R-021: affected=True`). Báo con số QC cho Người 4 điền README v2.
5. Viết `tools/trace_query.py`: đọc ticket + changelog + `jobs.csv` + `metadata.json` + `labels/`, ra `trace.json` (`tier_a`, `tier_b`, `notify`), guideline lấy **theo job**.
6. Viết REPORT mục 3 (QC v1, kết luận, vì sao R-021 phải xem lại hoặc train lại) và mục 5 (tiêu chí tầng a/b, vì sao lấy guideline theo job).

**Trong đề ẩn:** chạy `trace_query.py` ra `submission/de_an/trace.json` ngay sau khi có `delivery/`; phút 30–35 gộp review và chạy `merge_review.py` ra `submission/de_an/errors.json`; xem ảnh phần hàng đợi của mình.

---

## Người 4 (zenlylove) — Bàn giao v2, bảo mật, nộp bài

**Sở hữu:** `tools/build_handover.py`, thư mục `handover/<release_id>_v2/`, lineage release, `security.md`, `submission/TEAM.md`, tiêu đề README, REPORT mục 4 và 6, git và nộp bài.

Việc phải làm:
1. Viết `tools/build_handover.py` tạo lô v2 từ `delivery/` + `errors.json`, **không sửa `delivery/`**:
   - `images/`, `labels/`: chép nguyên byte, bỏ các ảnh lỗi nhãn detection hoặc thiếu file; ảnh chỉ lỗi panoptic ở lại.
   - `rework_queue.csv` (đúng annotator/reviewer theo `jobs.csv`), `manifest.csv` (sha256 thật), `label_summary.csv` (có `TOTAL`), `truyvet.csv` (guideline theo job, mỗi cảnh một split), `README.txt` theo mẫu.
   - Với `wrong_hash`: mở ảnh kiểm còn nguyên rồi ghi hash mới.
2. Chạy `pack_release.py`, `lineage.py record --event release --parent ...`, `check_handover.py --run runs/r83` cho tới khi **không còn FAIL**. Script phải chạy lại được ngay mỗi khi `errors.json` đổi.
3. Viết `runs/r83/security.md`: ca USB, năm việc được/không, ca khuôn mặt (Hold + báo người phụ trách, nêu tên ảnh thật có mặt người trong lô).
4. Viết REPORT mục 4 (hash chứng minh gì, không chứng minh gì) và mục 6 (bug lab nếu có).
5. Điền `submission/TEAM.md`, đổi tiêu đề `README.md` thành `# Day 10 Lab — Nhóm 83`, chạy `export_submission.py --run runs/r83`, kiểm checklist trong `SUBMISSION.md`, commit, push, nộp link LMS.

**Trong đề ẩn:** bấm giờ; xem ảnh phần hàng đợi của mình; phút 35–40 kiểm đủ 4 file trong `submission/de_an/`, bảo đảm không commit `delivery/`, commit và push.

---

## Việc chung của cả 4 người

- **Xem ảnh là việc của tất cả** (bắt buộc theo RULES): hàng đợi ứng viên ở seed luyện tập và đề ẩn chia đều 4 phần; mỗi người tự ghi kết luận `confirmed` / `rejected` cho phần của mình, note nói rõ thấy gì.
- **Commit:** mỗi người ít nhất 2 commit có nội dung, bằng tài khoản và email của chính mình, cho đúng phần mình sở hữu.
- **Vấn đáp:** mỗi người đọc hiểu cả code của người khác, vì người chấm hỏi ngẫu nhiên (một đoạn validator, một dòng review, một con số trong README v2).
- **AI:** dùng thoải mái để viết code, nhưng gửi prompt cho Người 1 ghi vào `prompts.md`. Không dùng AI thay việc xem ảnh.
- **Cấm:** đọc `_private/`, chạy `--dev-truth`, `--truth-dir`, sửa `scripts/`, sửa `delivery/`, dò điểm bằng nộp thử từng phần.
- **Diễn tập đề ẩn** một lần trước giờ G: tạo một seed lạ, bấm 40 phút, chạy đúng các vai trên.

## Mốc phụ thuộc giữa các người

| Ai chờ ai | Cần gì | Cách làm song song |
|---|---|---|
| Người 2 chờ Người 1 | khung nạp dữ liệu trong `validate.py` | Người 1 đẩy khung lên **trước tiên** (trong ~20 phút đầu) |
| Người 3, 4 chờ Người 1–2 | `errors.json` | Dùng tạm `errors.json` chỉ có lỗi luật để viết và thử công cụ; chạy lại khi có bản cuối |
| Người 4 chờ Người 3 | QC v1, lineage HOLD | Script v2 tự tính QC từ `errors.json`, không điền tay |

## Format dùng chung (để ghép code không vỡ)

`rules.json` (Người 1 ghi, Người 3 đưa vào `merge_review.py`):
```json
{"errors": [{"type": "wrong_hash", "target": "000000000139"}]}
```

`candidates.json` (Người 2 ghi, Người 3 chia hàng đợi):
```json
{"candidates": [{"image": "000000000139", "type": "class_swap",
                 "det_class": "car", "pan_class": "truck",
                 "box_px": [x0, y0, x1, y1], "segment_id": 123, "score": 0.91,
                 "reason": "box khớp segment, khác lớp"}]}
```

`review_log.csv` (cả nhóm ghi, Người 3 gộp):
```csv
image,type,verdict,note
000000000139,class_swap,confirmed,"[Người 2] xe tải mui kín, detection ghi car; panoptic ghi truck đúng"
```
