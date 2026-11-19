# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Người 4 (zenlylove) | Copilot SDK trong VS Code | Viết `tools/build_handover.py` tạo lô v2 từ `delivery/` và `errors.json`, giữ nguyên v1, tạo rework/manifest/thống kê/truy vết/README, và yêu cầu người dùng xác nhận ảnh `wrong_hash` sau khi xem bằng mắt. | AI không thể tự xác nhận bằng mắt ảnh `wrong_hash`; script bắt buộc người vận hành phân loại ảnh là còn nguyên hoặc hỏng. Chưa xác minh trên lô thật vì `errors.json` và run `r83` chưa sẵn sàng. | Chạy test tích hợp trên delivery giả lập, kiểm tra trường hợp giữ ảnh, rework, hash, sửa split/guideline; chạy bộ test repository. Cần chạy lại `check_handover.py` trên `runs/r83` khi lô thật sẵn sàng. |
