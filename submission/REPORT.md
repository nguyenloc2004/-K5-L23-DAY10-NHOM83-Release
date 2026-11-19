# Báo cáo nhóm 83

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): <<seed: ... / ... / ...>>
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): <<...>>

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
- **Hash (SHA-256) chứng minh được:**
  1. *Tính toàn vẹn (integrity) theo byte:* Cho phép xác minh chính xác từng byte của file (ảnh, nhãn, mask) có bị thay đổi, hư hỏng trong quá trình lưu trữ, nén/giải nén hoặc truyền tải mạng so với thời điểm ghi nhận trong manifest hay không.
  2. *Phát hiện sửa đổi hoặc nhầm lẫn file:* Giúp nhận diện ngay trường hợp file bị sửa đổi nội dung, đổi tên hoặc bị ghi đè nhầm file khác có cùng tên nhưng nội dung khác.
  3. *Tái lập và kiểm tra gói bàn giao:* Đóng gói lô v2 (`pack_release.py`) kèm mã checksum SHA-256 độc lập cho phép bên nhận đối soát và kiểm tra tự động mà không cần giải nén toàn bộ.

- **Hash KHÔNG chứng minh được:**
  1. *Tính đúng đắn ngữ nghĩa (semantic correctness):* File có hash khớp hoàn toàn không đồng nghĩa với việc bounding box được vẽ đúng vị trí, đúng đối tượng hoặc đúng lớp (class_id). Một nhãn gán sai lớp hoặc box bị lệch nghiêm trọng vẫn có hash hợp lệ nếu nội dung file đó không bị sửa đổi sau khi hash được tạo.
  2. *Tính tuân thủ quy chuẩn (guideline compliance):* Hash không đảm bảo ảnh hoặc nhãn tuân thủ đúng phiên bản quy định gán nhãn của dự án (ví dụ: vi phạm quy tắc làm mờ khuôn mặt hoặc vi phạm quy định gán nhãn mới).
  3. *Nguồn gốc và tính xác thực (authenticity / provenance):* Nếu cả file và manifest bị kẻ xấu hoặc sự cố ghi đè đồng thời thì hash so khớp vẫn hợp lệ mà không phát hiện được giả mạo, trừ khi có cơ chế chữ ký số (digital signature) hoặc khóa xác thực bảo vệ manifest.

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- **Kết quả kiểm thử quy trình bàn giao trên `runs/r83`:**
  - Quy trình bàn giao v2 với script `tools/build_handover.py` thực thi ổn định, đúng chuẩn định dạng; bộ kiểm `scripts/check_handover.py --run runs/r83` đạt kết quả tối đa **17/17 PASS, 0 FAIL**.
  - Các công cụ đi kèm (`pack_release.py`, `lineage.py`, `score_findings.py`, `export_submission.py`) vận hành trơn tru và nhất quán, tự đo đạt F1 tổng ≈ 1.0 (lỗi luật ≈ 1.0, lỗi gán nhãn ≈ 0.9, truy vết F1: tier_a 1.0, tier_b 1.0, notify 1.0).
- **Điểm lưu ý khi thực hiện (Operational Notes):**
  - Trong trường hợp ảnh bị lỗi `wrong_hash` (ví dụ `000000008021`), cần phải mở kiểm tra ảnh thực tế trước: nếu file ảnh vẫn nguyên vẹn (mở được bình thường, không bị corrupt) thì nguyên nhân do manifest v1 ghi sai hash -> giải pháp là giữ ảnh lại v2 và cập nhật sha256 thật vào manifest v2; nếu file bị hỏng thực sự mới chuyển sang `rework_queue.csv`.
  - Phân định rõ ràng giữa lỗi nhãn detection (bỏ khỏi v2, đưa vào rework) và lỗi chỉ thuộc panoptic (nhãn detection vẫn hợp lệ nên giữ nguyên ảnh trong v2 và ghi chú bàn giao cho team panoptic).
- **Kết luận:** Không phát hiện lỗi mã nguồn (bug) trong harness của lab Day 10.
