# ITS_Group3 – Phần việc Thành viên 2

Bộ phần việc này bổ sung hai mô-đun `sumo_connector.py` và `incident_injector.py`, đồng thời cung cấp nội dung báo cáo và sơ đồ Data Flow Diagram. Các tệp mạng đường, luồng xe, cảm biến và cấu hình gốc của Thành viên 1 được giữ nguyên.

## 1. Cấu trúc thư mục

Đặt hai tệp Python và thư mục `tests/` vào thư mục gốc của repository, cùng cấp với các tệp mô hình hiện có:

```text
ITS_Group3/
├── highway.net.xml                 # Mạng đường của Thành viên 1
├── highway.add.xml                 # Cảm biến E1 của Thành viên 1
├── highway_sparse.rou.xml          # Luồng xe thưa
├── highway_dense.rou.xml           # Luồng xe đông
├── highway_sparse.sumocfg
├── highway_dense.sumocfg
├── sumo_connector.py               # Thành viên 2
├── incident_injector.py            # Thành viên 2
├── tests/
│   ├── test_incident_injector.py
│   └── test_sumo_connector.py
└── output/
    └── member2/
        ├── K1_sparse_with_incident/
        ├── K2_dense_with_incident/
        ├── K3_dense_without_incident/
        └── member2_experiment_summary.csv
```

## 2. Cài đặt

1. Cài đặt Eclipse SUMO và bảo đảm có thể chạy lệnh `sumo --version`.
2. Sử dụng Python 3.10 trở lên.
3. Nếu Python chưa tìm thấy thư viện TraCI, cài đặt bằng lệnh:

```bash
python -m pip install traci
```

4. Nếu cài SUMO nhưng Python chưa tìm thấy TraCI, đặt biến môi trường `SUMO_HOME` trỏ đến thư mục cài đặt SUMO. Chương trình sẽ thêm thư mục `tools` vào Python path. Đồng thời, thêm thư mục `bin` của SUMO vào `PATH` để gọi được `sumo` và `sumo-gui`.

Ví dụ PowerShell (cần sửa đường dẫn theo máy tính):

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:Path += ";$env:SUMO_HOME\bin"
```

Không cần sửa các tệp `.net.xml`, `.rou.xml`, `.add.xml` và `.sumocfg` gốc của Thành viên 1.

## 3. Chạy các kịch bản

Chạy lần lượt cả ba kịch bản bằng SUMO không giao diện:

```bash
python sumo_connector.py --scenario all
```

Chạy một kịch bản riêng:

```bash
python sumo_connector.py --scenario k1
python sumo_connector.py --scenario k2
python sumo_connector.py --scenario k3
```

Mở SUMO-GUI để quan sát K2:

```bash
python sumo_connector.py --scenario k2 --gui
```

Đặt seed khác để lặp lại thí nghiệm (seed này được áp dụng cho SUMO và bộ chọn xe):

```bash
python sumo_connector.py --scenario all --seed 123
```

Nếu SUMO executable không nằm trong `PATH`, truyền đường dẫn rõ ràng:

```bash
python sumo_connector.py --scenario k1 --sumo-binary "C:\\SUMO\\bin\\sumo.exe"
```

## 4. Thiết lập ba kịch bản

| Mã | Tệp luồng xe | Tiêm sự cố | Mục đích |
|---|---|---|---|
| K1 | `highway_sparse.rou.xml` | Có | Kiểm tra phản ứng khi lưu lượng thưa |
| K2 | `highway_dense.rou.xml` | Có | Kiểm tra phản ứng khi lưu lượng cao điểm |
| K3 | `highway_dense.rou.xml` | Không | Đối chứng: phân biệt bất thường do mật độ cao tự nhiên với sự cố |

Các giá trị mặc định của sự cố nhân tạo trong code:

| Tham số | Giá trị mặc định | Giải thích |
|---|---:|---|
| Thời điểm dự kiến | 900 s | Bắt đầu tiêm sau 15 phút mô phỏng |
| Vị trí mục tiêu | 1.750 m | Trung điểm giữa S3 (1.500 m) và S4 (2.000 m) |
| Bán kính tìm xe | 125 m | Xe phải nằm trong đoạn 1.625–1.875 m |
| Thời gian giữ xe dừng | 300 s | Giữ sự cố trong 5 phút |
| Thời gian chờ tối đa | 120 s | Nếu chưa có xe phù hợp, tiếp tục tìm; quá thời hạn sẽ ghi nhận không tiêm được |
| Bước mô phỏng | 1 s | Đọc từ cấu hình `.sumocfg` hiện có |
| Chu kỳ E1 | 30 s | Đọc từ `highway.add.xml` hiện có |

Thời điểm, vị trí, bán kính, thời lượng và thời gian chờ là tham số mặc định do nhóm đặt ra để tổ chức thực nghiệm, không phải số liệu đo đạc ngoài thực tế. Có thể điều chỉnh trong `IncidentConfig`.

## 5. Cơ chế tiêm sự cố

1. Sau mỗi lần `traci.simulationStep()`, `sumo_connector.py` đọc thời gian mô phỏng hiện tại.
2. Khi thời gian đạt 900 giây, `IncidentInjector` quét danh sách xe đang hoạt động.
3. Chỉ xe trên cạnh `E_main`, đang di chuyển và có vị trí dọc làn trong khoảng 1.625–1.875 m mới được đưa vào danh sách ứng viên.
4. Chương trình chọn ngẫu nhiên một xe trong danh sách bằng bộ tạo số ngẫu nhiên có seed để có thể lặp lại kết quả.
5. Chương trình lưu speed mode gốc, tạm đặt speed mode bằng 0 (nếu bật tùy chọn), sau đó gọi `traci.vehicle.setSpeed(veh_id, 0)` để tạo trạng thái xe dừng.
6. Khi hết 300 giây, chương trình gọi `traci.vehicle.setSpeed(veh_id, -1)` và khôi phục speed mode ban đầu.
7. Nếu không tìm được xe phù hợp, bộ tiêm tiếp tục tìm tối đa 120 giây. Hết thời gian chờ thì ghi trạng thái `not_injected`, không giả định rằng sự cố đã xảy ra.

Đây là tình huống dừng xe được tạo bằng lệnh điều khiển trong mô phỏng. Tùy chọn speed mode bằng 0 tắt các kiểm tra tốc độ của SUMO đối với xe được chọn trong thời gian sự cố, vì vậy xe có thể dừng đột ngột hơn hành vi phanh thực tế. Cần nêu rõ giới hạn này khi thảo luận kết quả.

## 6. Tệp đầu ra

Mỗi kịch bản có một thư mục riêng trong `output/member2/`:

- `member2_run.sumocfg`, `member2_highway.add.xml`: cấu hình phụ được tạo tự động cho lần chạy đó.
- `e1_S1.xml` … `e1_S7.xml`: dữ liệu đầu ra từ cảm biến E1 của kịch bản.
- `incident_events.csv`: mã xe, thời điểm, vị trí, làn và trạng thái sự cố. K3 cũng có tệp này nhưng chỉ có hàng tiêu đề.
- `incident_summary.json`: tóm tắt trạng thái tiêm sự cố và tham số đã dùng.
- `run_summary.json`: tóm tắt thời gian mô phỏng, số bước, seed và trạng thái kịch bản.

`member2_experiment_summary.csv` tổng hợp các lượt chạy K1, K2 và K3. Những dữ liệu này là đầu vào để Thành viên 3 đọc tín hiệu cảm biến và Thành viên 4 tính toán chỉ số. `run_scenario()` có tham số `step_callback` để tích hợp logic xử lý theo từng bước; thuật toán California #7 và module đánh giá chưa được gộp vào mã nguồn của Thành viên 2.

## 7. Kiểm thử

Chạy kiểm thử logic Python mà không cần khởi động SUMO:

```bash
python -m unittest discover -s tests -v
```

Các kiểm thử xác nhận logic chọn xe, kích hoạt và giải phóng trạng thái dừng, hết thời gian chờ và tạo cấu hình đầu ra riêng. Muốn xác nhận mô phỏng thực tế, cần chạy lại cả ba kịch bản trên máy đã cài SUMO.
