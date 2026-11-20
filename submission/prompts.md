# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Người 1 (baodu1204) | Copilot/AI dùng code | Viết khung `validator/validate.py` với giao diện CLI cố định, nạp dữ liệu từ `delivery/`, chỉ dùng thư viện chuẩn, tạo `errors.json` và `candidates.json`, không đọc `_private/`, `data_source/` hoặc mạng. | Chưa xác minh trên dữ liệu thật; AI có thể đoán sai tên khoá JSON hoặc bỏ qua tối đa một lỗi mỗi ảnh. | Chạy giao diện CLI, kiểm mã không đọc thư mục cấm, chạy seed `83`, `11`, `22`, rồi chạy lô sạch và ghi F1/số lỗi thật. |
| 2 | Người 1 (baodu1204) | Copilot/AI dùng code | Thêm `missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`, `scene_leak`, `guideline_mismatch`, `invalid_category_id`, `thing_overlap` theo thứ tự ưu tiên, không hard-code tên ảnh hoặc đáp án seed. | Có thể tấn công ngưỡng hoặc parse sai trong dữ liệu; chưa chứng minh F1 bằng thử nghiệm. | Soát từng hàm với fixture nhỏ; chạy bộ test/validator trên `83`, `11`, `22` và `runs/clean`; ghi số liệu thực, không chỉnh `_private`. |
| 3 | Người 2 (Hung-1812) | Copilot/AI dùng code | Ghép box YOLO sau khi đổi sang pixel với segment panoptic thing non-crowd bằng tên lớp; dùng coverage pixel thay vì chỉ IoU bbox để sinh loại ứng viên yêu cầu. | AI có thể dùng IoU bbox sai ngữ cảnh hoặc tạo ngưỡng cố ý khớp seed. | Đo ứng viên trên `runs/clean`, thử seed `83`, `11`, `22`; xác nhận định dạng `candidates.json` và ràng buộc số hàng đợi bằng kết quả thật. |
| 4 | Người 2 (Hung-1812) | Copilot/AI dùng code | Sinh `class_swap`, `category_swap`, `bbox_drift`, `missing_box`, `instance_merge`, đo nhiễu tự nhiên, chọn ngưỡng và viết mục 1–2 REPORT bằng số liệu thực. | AI có thể bịa F1, số ứng viên hoặc lý do hiệu suất. | Đối chiếu trực tiếp file đầu ra; ghi `score_findings.py` chỉ để tự đo, không dò đáp án hoặc dùng `_private`. |
| 5 | Người 3 (nguyenloc2004) | Copilot/AI dùng code | Viết `tools/view.py` và `tools/review_queue.py`: vẽ box detection, viền segment panoptic, phóng to vùng vật, chia hàng đợi và gộp review. | AI có thể tạo note chung chung, nhãn sai hoặc bộ review không hiển thị tên người xem. | Chạy công cụ trên ảnh và candidates thật; kiểm note ≥20 ký tự, có tên người xem, không trùng nhau; người thật tự quyết định `confirmed/rejected`. |
| 6 | Người 3 (nguyenloc2004) | Copilot/AI dùng code | Viết `tools/trace_query.py` để đọc ticket, changelog, jobs, metadata và labels, rồi tạo `trace.json` gồm `tier_a`, `tier_b`, `notify`; guideline phải lấy theo job. | AI có thể lấy guideline theo scene thay job hoặc thiếu dữ liệu theo từng tầng. | Chạy trace trên run thật; kiểm trace bằng ticket/changelog/jobs/metadata/labels tương ứng và kiểm từng mục trong REPORT. |
| 7 | Người 3 (nguyenloc2004) | Copilot/AI dùng code | Gộp `review_log.csv` bằng `merge_review.py`, tính QC, ghi lineage HOLD và chạy impact để xác nhận `R-021` bị ảnh hưởng. | AI có thể ghi nhầm người xem, kết luận review hoặc tự tạo con số QC. | Đối chiếu review gốc, `errors.json`, script merge và lineage thật; chỉ ghi con số xuất ra công cụ. |
| 8 | Người 4 (zenlylove) | Copilot/AI dùng code | Viết quy trình bàn giao v2 giữ byte `delivery/`, lọp ảnh theo `errors.json`, tạo rework/manifest/summary/truy vết/README và `security.md`. | AI không thể thay người kiểm ảnh `wrong_hash`, không được suy ra hash mới hoặc khẳng định USB/xem khuôn mặt khi chưa có dữ liệu. | Chạy lại script sau mỗi thay đổi `errors.json`; xác minh bằng mắt; chạy `pack_release.py`, `check_handover.py` đến khi không còn FAIL. |
| 9 | Người 4 (zenlylove) | Copilot SDK trong VS Code | Viết `tools/build_handover.py` tạo lô v2 từ `delivery/` và `errors.json`, giữ nguyên v1, tạo rework/manifest/thống kê/truy vết/README, và yêu cầu người dùng xác nhận ảnh `wrong_hash` sau khi xem bằng mắt. | AI không thể tự xác nhận bằng mắt ảnh `wrong_hash`; script bắt buộc người vận hành phân loại ảnh là còn nguyên hoặc hỏng. Chưa xác minh trên lô thật vì `errors.json` và run `r83` chưa sẵn sàng. | Chạy test tích hợp trên delivery giả lập, kiểm tra trường hợp giữ ảnh, rework, hash, sửa split/guideline; chạy bộ test repository. Cần chạy lại `check_handover.py` trên `runs/r83` khi lô thật sẵn sàng. |

## Prompt đầy đủ theo từng mảng

> Các prompt dưới đây là bản tự tạo theo `PhanCong.md` để thành viên dùng và kiểm lại. Chỉ ghi một prompt vào nhật ký sau khi thành viên xác nhận đã dùng; không coi AI thay cho review ảnh của người.

### Người 1 — Validator và gom prompt

```text
Bạn là trợ lý lập trình cho bài lab. Hãy giúp tôi làm việc trong `validator/validate.py`,
tuân thủ giao diện `python validator/validate.py <delivery> --out <errors.json>
[--candidates <candidates.json>]`.

Chỉ đọc thư mục delivery được truyền vào. Không đọc `_private/`, `data_source/`,
annotation đáp án seed, không dùng mạng và không hard-code tên ảnh.
Chỉ dùng thư viện chuẩn; có thể import `scripts/pngutil.py`.
Viết đủ 9 kiểm: missing_image, wrong_hash, invalid_class, bbox_out_of_bounds,
duplicate_box, scene_leak, guideline_mismatch, invalid_category_id, thing_overlap.
Mỗi ảnh chỉ giữ tối đa một lỗi theo thứ tự ưu tiên rõ ràng.
Nạp manifest, metadata, jobs, classes, panoptic, YOLO labels và đếm pixel mask.
Giải thích thay đổi, không tự tạo số liệu F1 hoặc bịa dữ liệu kiểm thử.
Hãy chỉ thay file liên quan đến validator và ghi rõ cách chạy/test.
```

```text
Hãy tạo fixture nhỏ và chạy validator trên seed 83, 11, 22 cùng lô sạch.
Không dùng `_private`, không chạy chế độ --dev-truth hoặc --truth-dir,
không dò đáp án bằng cách nộp từng phần và xem điểm đổi.
Ghi kết quả thật ra terminal. Với seed sạch, xác nhận không còn cảnh báo lỗi luật.
Ghi bản prompt, chỗ AI có thể sai, và cách nhóm kiểm lại vào
`submission/prompts.md`.
```

### Người 2 — Detection ↔ panoptic

```text
Hãy giúp tôi hoàn thiện phần cross-check trong `validator/validate.py`.
Đổi box YOLO sang pixel, ghép box với segment thing non-crowd, ghép lớp qua tên
trong classes.txt và categories thay vì so sánh ID nếu có thể.
Chỉ dùng tỉ lệ pixel mask nằm trong box cùng các điểm coverage/bbox phù hợp
để sinh class_swap/category_swap, bbox_drift, missing_box và instance_merge.

Ghi candidates đúng cấu trúc dùng chung:
{"candidates":[{"image":...,"type":...,"det_class":...,"pan_class":...,
"box_px":[...],"segment_id":...,"score":...,"reason":"..."}]}

Không chọn ngưỡng bằng `_private` hoặc kết quả dò điểm.
Hãy đo trên runs/clean và ghi toàn bộ ngưỡng cùng số ứng viên đầu ra.
```

```text
Thử toàn bộ kiểm tra cross-check trên nhiều seed, gồm 83, 11 và 22.
Không được bịa F1 hoặc số lượng ứng viên.
Viết mục 1–2 của `submission/REPORT.md` bằng số thật:
F1 theo seed, ứng viên lô sạch, ngưỡng đã chọn, cách chọn và lý do nhiều ứng viên
có thể làm F1 giảm.
```

### Người 3 — Review, truy vết và lineage

```text
Viết hoặc sửa `tools/view.py` để mở ảnh theo tên, vẽ box detection kèm tên lớp
và viền segment panoptic kèm tên lớp. Hỗ trợ phóng to vùng vật để người xem ảnh
đặt confirmed/rejected. Công cụ không được thay kết luận bằng AI.
Viết `tools/review_queue.py` để chia candidates thành các phần cho 4 người
và gộp review_log.csv. Mỗi dòng có image,type,verdict,note và tên người xem;
note dài tối thiểu 20 ký tự, mô tả rõ vật thật, không chép giống nhau.
```

```text
Viết `tools/trace_query.py` đọc ticket, changelog, jobs.csv, metadata.json
và labels để tạo trace.json với tier_a, tier_b và notify.
Guideline phải được lấy theo job của từng ảnh/cảnh, không mặc định một guideline chung.
Không thêm dữ liệu có nguồn ngoài các file đã nêu.
Sau đó ghi cách kiểm lại từ ticket đến dòng truy vết.
```

```text
Hãy mô tả quy trình chạy merge review:
1) gom review_log.csv của cả 4 người;
2) chạy script merge để tạo errors.json;
3) chạy score_findings.py chỉ để tự đo;
4) tính QC v1;
5) ghi lineage HOLD và chạy lineage impact;
6) xác nhận R-021 có affected=True.

Không tự suy đoán kết quả; chỉ ghi số liệu và trạng thái xuất ra từ file/công cụ thật.
Viết mục 3 và 5 của REPORT bằng dữ liệu thật.
```

### Người 4 — Bàn giao, bảo mật và nộp bài

```text
Viết `tools/build_handover.py` tạo lô v2 từ delivery và errors.json.
Không sửa delivery. Giữ byte ảnh/label v1, bỏ ảnh có lỗi nhãn detection hoặc thiếu file,
giữ ảnh chỉ lỗi panoptic.
Tạo rework_queue.csv theo annotator/reviewer trong jobs.csv, manifest.csv với SHA-256 thật,
label_summary.csv có TOTAL, truyvet.csv lấy guideline theo job và split cho mỗi cảnh,
README.txt theo mẫu.
Với wrong_hash, bắt buộc người vận hành mở ảnh bằng mắt và truyền --wrong_hash_good
hoặc --wrong_hash_corrupt. Không tự khẳng định ảnh còn nguyên hay hỏng.
Script phải chạy lại được sau khi errors.json thay đổi.
```

```text
Chuẩn bị quy trình bàn giao theo seed r83:
chạy build_handover, pack_release, lineage release với parent đúng,
security.md, điền TEAM.md, đổi tiêu đề README thành Nhóm 83,
chạy export_submission và check_handover cho tới khi không còn FAIL.
Không sửa scripts để qua kiểm tra, không commit delivery/, runs/, *.zip hoặc secret.
Không bịa hash, người gán/kiểm, số QC hoặc kết luận bảo mật.
Trong security.md ghi đúng ca USB, năm việc được/không và ca khuôn mặt,
thêm tên ảnh thật có mặt người chỉ khi dữ liệu xác nhận.
```
