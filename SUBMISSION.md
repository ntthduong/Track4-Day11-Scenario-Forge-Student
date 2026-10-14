# Bài nộp Scenario Forge — 2A202602905

## Tái lập trên Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\Run-Lab.ps1 all
.\.venv\Scripts\python.exe tools/build_report.py
.\.venv\Scripts\python.exe tools/validate_submission.py
```

MSSV thật có chữ `A`. Bộ chạy gốc chỉ chấp nhận chữ số khi đọc `REPORT.md`, nhưng hỗ trợ `LAB11_MSSV` trực tiếp. `Run-Lab.ps1` đọc nguyên MSSV trong báo cáo và đặt biến này trong lúc chạy, rồi khôi phục giá trị trước đó. Không đổi MSSV, hash, seed, `run_all.py` hay lõi mô phỏng. Grader cần truyền **nguyên chuỗi `2A202602905`** qua `LAB11_MSSV`, đúng cơ chế roster đã có trong bộ chạy.

Trên Linux/macOS, sau khi cài requirements:

```bash
LAB11_MSSV=2A202602905 python run_all.py all
```

`requirements-lock.txt` ghi môi trường tạo bài nộp; `requirements.txt` gốc được giữ nguyên. Node.js dùng cho test parity; trình xem 3D không cần mạng. Bản evidence nộp dùng toàn bộ ngân sách mặc định, không `--quick`, không `LAB11_TEST_SALT`.

## Xem kết quả

Mở `viewer/index.html` trong trình duyệt. Chương 9 nhận `evidence/viewer.json`; chương 10 nhận `hazard.json`. `evidence/comparison_viewer.json` là ví dụ bổ sung: xe chính dùng policy được chọn, bóng mờ dùng policy gốc, giúp đọc ảnh câu 6 rõ ràng.

`REPORT.md` trả lời 9 câu bằng số của pipeline. `evidence/shots/` chứa ảnh chụp thật từ trình xem 3D. Các script trong `tools/` hỗ trợ thiết kế và đối chiếu, không sửa thí nghiệm chấm điểm.

`build_report.py` đọc kết quả, dựng bảng và xuất ví dụ quỹ đạo bổ sung. `caution_counterexample.py` tìm ca policy cautionV=5 phản tác dụng trong chính draw TRAIN đã có, không dùng TEST để chọn policy; dữ liệu và trình xem riêng nằm ở `evidence/caution_counterexample.json` và `caution_viewer.json`. `validate_submission.py` kiểm tra MSSV/seed/ngân sách, phép cộng xác suất, chọn policy từ TRAIN, scene/hazard, ảnh, test và các file mô phỏng nguyên bản. `evidence/manifest.json` chứa SHA-256 của evidence tại lần kiểm tra, chuẩn hóa CRLF thành LF cho JSON/TXT và giữ nguyên bytes ảnh để dùng được trên cả Windows/Linux. Thời gian chạy trong JSON có thể khác khi tái lập, nên so các trường khoa học thay vì đòi hash của một lần chạy mới giống hệt. Nếu đổi môi trường hoặc tạo lại ví dụ, kiểm tra lại ảnh với trình xem.

## Phạm vi của hazard và exposure

Hazard là xe đạp chuyển ngang gần hết một làn để tránh vùng cản ở mép đường. Vùng cản là bối cảnh giải thích, không phải một tác nhân được mô phỏng. `space` là dải kiểm thử kỹ thuật có căn cứ hình học/gia tốc và một phép quét thiết kế riêng; không phải phân phối hành vi được fit từ dữ liệu thật.

`exposure=1` có nguồn từ **giao thức thử có kiểm soát**: mỗi chuyến mô phỏng được cài đúng một xe đạp H0. Nó không phải tần suất gặp xe đạp lạng ra trong giao thông thực. Vì vậy `mine.json: per_trip` chỉ diễn tả chuyến thử cố ý phơi nhiễm này. Báo cáo đưa công thức theo exposure thực và ngưỡng so sánh, không coi phép nhân này là dự báo ngoài đời. Chưa có dữ liệu thực để ước lượng exposure ngoài giao thức.

Rubric trong repo chấm tối đa 100, không quy định bonus riêng. Kiểm tra bổ sung, ghi môi trường tái lập và phân tích exposure là phần mở rộng kỹ thuật; không tự nhận điểm bonus.
