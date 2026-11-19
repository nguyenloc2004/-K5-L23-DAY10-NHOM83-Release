# Bảo mật khi làm việc — Nhóm 83

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Tuyệt đối không chép dữ liệu của lô dự án ra USB cá nhân, không gửi qua email cá nhân và không tải lên các dịch vụ đám mây bên ngoài, kể cả với mục đích muốn làm tiếp ở nhà cho kịp tiến độ. Việc đưa dữ liệu ra khỏi môi trường kiểm soát vi phạm nghiêm trọng chính sách bảo mật thông tin, có nguy cơ làm lộ lọt dữ liệu khách hàng và vi phạm cam kết bảo mật (NDA). Khi hết giờ làm việc mà chưa hoàn thành, cần lưu lại trạng thái công việc trên hệ thống được chỉ định, báo cáo trực tiếp với người phụ trách (lead/PM) để xin gia hạn thời gian hoặc xin cấp quyền truy cập từ xa an toàn (VPN/VDI) trên thiết bị được công ty phê duyệt.

## 2. Năm việc: được hay không
1. Mở job được giao trên máy công ty: **Được**, vì đây là môi trường làm việc hợp lệ và được cấp quyền để thực hiện công việc gán nhãn theo phân công.
2. Chụp màn hình gửi người quen: **Không được**, vì hình ảnh dữ liệu và nhãn thuộc quyền sở hữu bảo mật của dự án, việc phát tán ra ngoài dù dưới bất kỳ hình thức nào đều vi phạm bảo mật.
3. Chép lô ra USB cá nhân: **Không được**, vì thiết bị lưu trữ cá nhân không được mã hóa, không có kiểm soát truy cập và dễ gây thất thoát dữ liệu.
4. Dán nhãn thật lên chatbot công khai: **Không được**, vì các chatbot bên ngoài có thể lưu lại dữ liệu và dùng cho huấn luyện, làm rò rỉ dữ liệu nhạy cảm ra ngoài biên giới kiểm soát.
5. Đưa tài khoản CVAT cho đồng nghiệp: **Không được**, vì tài khoản định danh gắn liền với trách nhiệm cá nhân, quyền hạn và truy vết lịch sử; việc chia sẻ tài khoản vi phạm quy tắc định danh và kiểm toán an toàn thông tin.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Khi phát hiện ảnh có khuôn mặt người nhìn rõ trong lô mà guideline yêu cầu phải làm mờ để bảo vệ quyền riêng tư, hành động ngay là đặt trạng thái lô là **Hold** và báo cáo ngay cho người phụ trách (Lead/QA/PM) qua kênh liên lạc chính thức của dự án. Người gán nhãn hoặc kiểm thử không được tự ý dùng công cụ cá nhân để làm mờ hay tự xóa ảnh khỏi thư mục, vì việc đó sẽ làm sai lệch dữ liệu gốc, phá vỡ tính toàn vẹn (hash sha256), sai lệch manifest và vượt thẩm quyền quy định. Trong lô `runs/r83/delivery`, các ảnh thực tế có khuôn mặt người nhìn rõ cần xử lý che mờ theo quy định gồm có: `000000000139` (người trong phòng), `000000000785` và `000000000872`.
