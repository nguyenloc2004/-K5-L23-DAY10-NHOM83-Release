# Làm đề ẩn (40 phút)

Nộp trong `submission/de_an/`: `errors.json`, `candidates.json`, `review_log.csv`, `trace.json`. Không commit `delivery/`.

## 1. Nhận đề

Tải `de_an.zip` ở tab **Releases** của repo đề, giải nén vào thư mục gốc repo → có `delivery/`.

## 2. Chạy validator

```powershell
py -X utf8 validator/validate.py delivery --out submission/de_an/errors.json --rules-out submission/de_an/rules.json --candidates submission/de_an/candidates.json
```

## 3. Truy vết

```powershell
py -X utf8 tools/trace_query.py delivery --out submission/de_an/trace.json
```

## 4. Tạo file review

```powershell
py -X utf8 tools/review_queue.py split submission/de_an/candidates.json --out submission/de_an/review --people solo
```

## 5. Push bản an toàn (lỗi luật + trace)

```powershell
git add submission/de_an
```

```powershell
git commit -m "De an: loi luat + trace"
```

```powershell
git push
```

## 6. Vẽ ảnh ứng viên

```powershell
py -X utf8 tools/view.py delivery --review submission/de_an/review/review_solo.csv --out view_de_an
```

Phóng to một vùng khi vật nhỏ (đổi tên ảnh và toạ độ):

```powershell
py -X utf8 tools/view.py delivery img_0001 --crop 0 0 200 200 --out view_de_an --open
```

## 7. Xem ảnh, điền `submission/de_an/review/review_solo.csv`

- `verdict`: `confirmed` hoặc `rejected`. Không xem kịp thì để trống.
- `note`: ≥ 20 ký tự, nói thấy gì, mỗi dòng khác nhau.
- `type` theo điều thấy trong ảnh:

| Thấy | type |
|---|---|
| detection sai lớp | `class_swap` |
| panoptic sai lớp | `category_swap` |
| box lệch khỏi vật | `bbox_drift` |
| vật không có box | `missing_box` |
| 2 vật gộp 1 segment | `instance_merge` |

Mỗi ảnh tối đa 1 lỗi confirmed. Phút 32 dừng xem.

## 8. Gộp review

```powershell
py -X utf8 tools/review_queue.py merge submission/de_an/review --out submission/de_an/review_log.csv --force
```

## 9. Chốt errors.json

```powershell
py -X utf8 scripts/merge_review.py --rules submission/de_an/rules.json --review submission/de_an/review_log.csv --out submission/de_an/errors.json
```

## 10. Nộp

```powershell
git add submission/de_an
```

```powershell
git status
```

```powershell
git commit -m "De an: errors, candidates, review_log, trace"
```

```powershell
git push
```

`git status` không được có `delivery/` hay `view_de_an/`.
