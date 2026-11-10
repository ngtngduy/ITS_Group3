# BÁO CÁO CÔNG VIỆC - THÀNH VIÊN 3 (PHÁT HIỆN SỰ CỐ & THUẬT TOÁN CALIFORNIA)

Phần việc của Thành viên 3 chịu trách nhiệm tích hợp thuật toán phát hiện sự cố, chạy mô phỏng qua các kịch bản và xuất file kết quả dưới dạng JSON phục vụ cho toàn bộ dự án nhóm ITS_Group3.

---

## 1. Cấu trúc thư mục (`output/member3/`)
Toàn bộ mã nguồn và kết quả của Thành viên 3 nằm gọn trong thư mục `output/member3/`:
* `run_detection.py`: Script chính điều phối việc chạy mô phỏng và phát hiện sự cố theo kịch bản.
* `california_algo.py`: Thuật toán phát hiện sự cố California (California Incident Detection Algorithm).
* `detector_reader.py`: Đọc và xử lý dữ liệu từ các bộ cảm biến (induction loops).
* `detected_incidents_k1.json`: Kết quả phát hiện sự cố cho kịch bản K1 (Thưa/Có sự cố).
* `detected_incidents_k2.json`: Kết quả phát hiện sự cố cho kịch bản K2 (Đông/Có sự cố).
* `detected_incidents_k3.json`: Kết quả đối chứng cho kịch bản K3 (Đông/Không sự cố – chuẩn hóa trả về mảng rỗng `[]`).

---

## 2. Hướng dẫn chạy mô phỏng và quét sự cố
Để tái lập hoặc chạy kiểm tra lại kết quả trên máy cá nhân, các thành viên thực hiện các bước sau từ thư mục gốc của dự án:

1. **Sinh lại các tệp cấu hình mô phỏng chuẩn di động (Portable):**
   ```cmd
   python sumo_connector.py --scenario k1
   python sumo_connector.py --scenario k2
   python sumo_connector.py --scenario k3