# Báo cáo nhóm 83

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): Chưa ghi đầu ra tự đo của seed `83`, `11` và `22` trong các file submission hiện có. Không được suy ra hoặc bịa F1: cần chạy lại `python scripts/score_findings.py --run runs/r83` bằng dữ liệu lô thật trong workspace rồi điền giá trị đầu ra.
- Số ứng viên trên lô clean (`--no-faults`): Không có file kết quả lô clean trong thư mục submission hiện có, nên số này chưa thể xác nhận.
- Hàng đợi trên seed luyện tập `83`: 39 dòng ứng viên trong `submission/r83/candidates.json`.
- Kết quả xem ảnh: 8 ứng viên `confirmed`, 31 ứng viên `rejected`; 39 ứng viên tương ứng với 39 dòng trong `review_log.csv`.
- Ngưỡng đã chọn và cách chọn: Validator dùng ngưỡng coverage và bbox đã cấu hình trong `CC_*` của `validator/validate.py`, ghép bằng pixel mask thay vì chỉ IoU bbox. Việc chọn ngưỡng dựa trên lô clean và nhiều seed, không dùng `_private` để chọn hoặc dò đáp án. Do file kết quả đo lô clean/ngưỡng không được export vào `submission/`, số liệu chi tiết ngưỡng đầu ra cần đối chiếu lại với file source khi nộp.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Trong seed `83`, bắt đầu có 39 ứng viên. Sau khi xem ảnh, 31 ứng viên là lệch tự nhiên hoặc che khuất/biên mask không phải lỗi và bị `rejected` (31/39 ≈ 79,5%); 8 ứng viên là lỗi thật được `confirmed` (8/39 ≈ 20,5%). Nếu giữ toàn bộ ứng viên mà không review, hệ thống sẽ coi những 31 trường hợp `rejected` là false positive, làm precision và F1 cross-check giảm.

Ngược lại, nếu bỏ qua ứng viên quá sớm thì có nguy cơ bỏ sót lỗi đã xác nhận bằng ảnh. Vì vậy cần giữ ngưỡng đủ rộng để không bỏ sót, nhưng không để hàng đợi bùng nổ so với số ảnh người xem xử lý trong thời gian quy định.

## 3. Quyết định và lineage
Lô v1 có `21` mục lỗi trong `submission/r83/errors.json` trên tổng `250` ảnh, nên QC v1 = `21/250 = 8.4%`. Theo ngưỡng Day 7 (trên 2% thì không Release), quyết định là **HOLD**.

Lineage ghi trạng thái v1 là `HOLD`, release v2 có parent là release v1; chạy impact theo release v1 dự kiến cho kết quả `R-021: affected=True action=review_or_retrain`. `R-021` đã train trên dataset v1 nên dữ liệu/model không tự thay đổi khi phát hiện lỗi: run này cần xem lại dữ liệu huấn luyện, kết quả đánh giá và huấn luyện lại nếu ảnh hưởng đến phân phối nhãn.

- Release v1: `lab250_5a5e3b0b91e9`
- Release v2: `lab250_5a5e3b0b91e9_v2`
- Training run bị ảnh hưởng: `R-021`

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
File `submission/r83/trace.json` đã phân loại:
- `tier_a`: `000000000724`, `000000007088` — ảnh thuộc cảnh AI nêu trong ticket, job dùng guideline cũ và có ít nhất một box thuộc lớp bị đổi quy tắc.
- `tier_b`: `000000001532`, `000000006040`, `000000006723`, `000000007386` — các ảnh khác cùng điều kiện mới/đổi quy tắc nhưng chưa có báo cáo trực tiếp.
- `notify`: `A03`, `A05`, `Q02` — mã annotator/reviewer xuất hiện trong job chứa ảnh tier a/b.

Guideline lấy từ `guideline` của từng job trong `jobs.csv`, không lấy guideline ghi ở từng ảnh/metadata. Việc lấy theo ảnh có thể chính là sai ở `guideline_mismatch`; lấy theo job mới xác định được quy định áp dụng đúng cho người gán và người kiểm.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Lô v2 ghi nhận `238` ảnh, `1642` nhãn, với `12` ảnh đưa vào rework queue. `wrong_hash` của `000000008021` được ghi là ảnh còn nguyên sau khi người vận hành mở kiểm; v2 giữ ảnh và cập nhật SHA-256 mới.
- Nhãn detection hoặc thiếu file được bỏ khỏi v2 và đưa vào rework; các lỗi chỉ thuộc panoptic được ghi chú để team panoptic xử lý nhưng ảnh detection vẫn được giữ. Trong seed `83`, các ảnh panoptic giữ lại gồm `000000006723`, `000000006954`, `000000007818`, `000000015254`, `000000021903`.
- README của handover ghi kết luận v1 là **Hold** và kết luận v2 là **Release**. Không có đủ dữ liệu log chạy kiểm tra trong thư mục submission để tự xác nhận số lần PASS/FAIL tại thời điểm báo cáo; trước nộp nên chạy lại `python scripts/check_handover.py --run runs/r83` và sửa mọi FAIL.
- Các F1 theo seed, F1 cross-check, số ứng viên clean và kết quả trace tự đo cần được ghi lại từ chạy thật. Đây là điểm dữ liệu chưa có trong file export hiện tại; không khẳng định số F1 nếu chưa chạy script đo.
