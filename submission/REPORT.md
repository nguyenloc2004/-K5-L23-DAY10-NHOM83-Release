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
SHA-256 là dấu vân tay của nội dung file theo byte. So sánh hash với manifest giúp phát hiện file khác với bản đã được ghi nhận, chẳng hạn do thay đổi hoặc hỏng trong quá trình lưu/chuyển giao. Hash không chứng minh ảnh hay nhãn đúng về mặt nội dung, không chứng minh nhãn phù hợp với guideline, và cũng không xác nhận nguồn gốc nếu manifest/hash bị thay cùng với file.

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
Chưa kết luận có bug: chưa chạy quy trình bàn giao trên `runs/r83`. Sau khi tạo lô và chạy `check_handover.py`, cập nhật mục này nếu phát hiện lỗi hoặc điểm chưa rõ; không ghi bug nếu chưa có bằng chứng tái hiện.
