# Làm seed luyện tập 83

Làm trong `runs/r83/`, cuối cùng export sang `submission/r83/`. Không commit `runs/`.

Nộp trong `submission/r83/`: `errors.json`, `candidates.json`, `review_log.csv`, `trace.json`, `security.md`, `handover/`.

- Release v1: `lab250_2a7499ca84b8`
- Lô: `runs/r83/delivery` (250 ảnh)

## 1. Chạy validator

```powershell
py -X utf8 validator/validate.py runs/r83/delivery --out runs/r83/errors.json --rules-out runs/r83/rules.json --candidates runs/r83/candidates.json
```

Kiểm lô sạch phải ra 0 lỗi luật:

```powershell
py -X utf8 validator/validate.py runs/clean/delivery --out runs/clean/errors.json --candidates runs/clean/candidates.json
```

Ghi số ứng viên trên lô sạch vào `submission/REPORT.md`.

## 2. Truy vết

```powershell
py -X utf8 tools/trace_query.py runs/r83/delivery --out runs/r83/trace.json
```

## 3. Tạo file review (chia 4 người)

```powershell
py -X utf8 tools/review_queue.py split runs/r83/candidates.json --out runs/r83/review
```

Mỗi người nhận một file `runs/r83/review/review_<tên>.csv`.

## 4. Vẽ ảnh ứng viên

Mỗi người vẽ phần của mình (đổi tên file):

```powershell
py -X utf8 tools/view.py runs/r83/delivery --review runs/r83/review/review_nguyenloc2004.csv
```

Phóng to một vùng khi vật nhỏ (đổi tên ảnh và toạ độ):

```powershell
py -X utf8 tools/view.py runs/r83/delivery 000000000139 --crop 0 0 200 200 --open
```

Ảnh xuất ở `runs/r83/view/` (không commit).

## 5. Xem ảnh, điền file review của mình

- `verdict`: `confirmed` hoặc `rejected`.
- `note`: ≥ 20 ký tự, nói thấy gì, mỗi dòng khác nhau, tên người xem ở đầu note.
- Nên có vài dòng `rejected` kèm lý do (vật bị che, crowd).
- `type` theo điều thấy trong ảnh:

| Thấy | type |
|---|---|
| detection sai lớp | `class_swap` |
| panoptic sai lớp | `category_swap` |
| box lệch khỏi vật | `bbox_drift` |
| vật không có box | `missing_box` |
| 2 vật gộp 1 segment | `instance_merge` |

Mỗi ảnh tối đa 1 lỗi confirmed.

## 6. Gộp review

```powershell
py -X utf8 tools/review_queue.py merge runs/r83/review --out runs/r83/review_log.csv
```

## 7. Chốt errors.json và tự đo

```powershell
py -X utf8 scripts/merge_review.py --rules runs/r83/rules.json --review runs/r83/review_log.csv --out runs/r83/errors.json
```

```powershell
py -X utf8 scripts/score_findings.py --run runs/r83
```

Ghi F1 theo từng nhóm lỗi vào `submission/REPORT.md`. Chỉ dùng để tự đo, không nộp thử từng phần để dò điểm.

## 8. Quyết định v1 và lineage

Tỉ lệ lỗi v1 = số mục trong `errors.json` / 250. Trên 2% thì HOLD.

```powershell
py -X utf8 scripts/lineage.py record --event decision --release-id lab250_2a7499ca84b8 --decision HOLD
```

```powershell
py -X utf8 scripts/lineage.py impact --release-id lab250_2a7499ca84b8
```

Mong đợi: `R-021: affected=True action=review_or_retrain`.

## 9. Bàn giao v2

Mở ảnh `wrong_hash` (`000000008021`) kiểm trước. Còn nguyên thì dùng `--wrong-hash-good`, hỏng thì `--wrong-hash-corrupt`:

```powershell
py -X utf8 tools/view.py runs/r83/delivery 000000008021 --open
```

```powershell
py -X utf8 tools/build_handover.py --run runs/r83 --wrong-hash-good 000000008021
```

Kiểm và sửa phần Ghi chú trong `runs/r83/handover/lab250_2a7499ca84b8_v2/README.txt` (đã sửa gì: hash, guideline, split, và vì sao).

```powershell
py -X utf8 scripts/pack_release.py runs/r83/handover/lab250_2a7499ca84b8_v2
```

```powershell
py -X utf8 scripts/lineage.py record --event release --release-id lab250_2a7499ca84b8_v2 --parent lab250_2a7499ca84b8
```

```powershell
py -X utf8 scripts/check_handover.py --run runs/r83
```

Sửa mọi FAIL. Đổi file nào trong v2 thì chạy lại `pack_release.py`. Không sửa `delivery/` và `scripts/`.

## 10. Bảo mật

`security.md` đang nằm ở `submission/r83/`. Chép vào `runs/r83/` để bước export không thiếu file:

```powershell
Copy-Item submission/r83/security.md runs/r83/security.md
```

## 11. Export và nộp

```powershell
py -X utf8 scripts/export_submission.py --run runs/r83
```

```powershell
git add submission
```

```powershell
git status
```

```powershell
git commit -m "Seed 83: errors, review_log, trace, handover"
```

```powershell
git push
```

`git status` không được có `runs/`, `data_source/` hay file `.zip`.
