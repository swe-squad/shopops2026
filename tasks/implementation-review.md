# Kết quả rà soát triển khai

Phạm vi: `mock-data-server`, `cronjob-server`, bộ kiểm thử hai dịch vụ và workflow
CI riêng. Áp dụng `agent-skills:code-review-and-quality`; không merge hoặc deploy.

## Các vấn đề đã sửa

- **P1 — Tính nhất quán Lazada:** PATCH trạng thái gốc của đơn từng có thể mâu
  thuẫn với các dòng hàng. Đã kiểm tra cả trạng thái chuẩn hóa và trạng thái gốc;
  có kiểm thử tái hiện lỗi rồi xác nhận sửa.
- **P1 — Retry:** `MUTATION_IN_PROGRESS` phải giữ intent ở trạng thái chờ, không
  ghi nhận thành từ chối cuối cùng. Đã thêm trường hợp kiểm thử riêng.
- **P1 — Idempotency:** DELETE shop cần phát lại receipt sau khi shop bị xóa nhưng
  vẫn kiểm tra quyền merchant hiện tại. Intent lưu phạm vi đã được nguồn xác nhận;
  bộ kiểm thử HTTP xác nhận cùng run ID. Khóa admin không được dùng lại giữa CRUD
  và cập nhật mart settings.
- **P1 — Revision:** PATCH không thay đổi dữ liệu không được tăng source revision.
  Đã tách kết quả ghi có hiệu lực và vẫn lưu receipt cho lần gọi không thay đổi.
- **P1 — Lỗi upstream:** Error envelope sai cấu trúc không được gây lỗi xử lý
  ngoài dự kiến. Đã chuẩn hóa mã lỗi và bổ sung kiểm thử.
- **P1 — Dữ liệu trong log:** Tắt access log; lỗi validation/SQL/HTTP được chuẩn
  hóa. Kiểm thử container kiểm tra log không chứa số điện thoại hoặc mật khẩu thử.

## Ranh giới và tính đúng đắn

- Mỗi dịch vụ đóng gói migration/fixture riêng; không import mã của dịch vụ khác.
  Processor chỉ dùng HTTP để truy cập nguồn và không truy cập `mock.*`.
- Các tên relation/column đến từ danh sách cố định; giá trị SQL dùng tham số.
  Kiểm tra quyền hiện tại áp dụng cho core, mart, raw và số liệu run.
- Intent được commit trước HTTP mutation. Publication và trạng thái thành công
  commit cùng transaction. Kiểm thử kill/restart xác nhận nguồn chỉ ghi một lần.
- Có kiểm thử rollback khi lỗi muộn, raw bất biến, tombstone, revision cạnh tranh,
  snapshot nhất quán khi ghi, khóa queue và lịch dùng đồng hồ kiểm soát.
- Hợp đồng OpenAPI mô tả entity cụ thể, full composite keys, headers và các view.
  Dữ liệu regression lớn tách biệt với seed MVP.
- Mức tải hiện tại là demo nhỏ. Full sync, một worker và một replica là giới hạn
  triển khai đã thống nhất; không đưa thêm hệ thống queue/distributed worker.

## Bằng chứng cuối cùng

| Kiểm tra | Kết quả |
|---|---|
| Source PostgreSQL suite | 39 passed |
| Processor PostgreSQL suite | 40 passed |
| Bộ HTTP/container hoàn chỉnh | 9 passed |
| Ruff check / format | Cả hai dịch vụ và script root đạt |
| Image build với context từng dịch vụ | Cả hai đạt; migration/seed chạy từ image |
| Seed MVP | 10 users, 7 merchants, 21 shops, 140 đơn; mỗi user thấy 20 |
| Regression lớn | 1.344 đơn, 1.400 dòng, 29 candidates (10/10/9), control = 0 |
| Workflow mới | YAML, quyền `contents: read`, path filters đã kiểm tra cục bộ |
| Chặn DB không dành cho test | Cả hai từ chối trước khi kết nối |

Máy Windows không có `make`; đã chạy các lệnh Python/Ruff tương đương các target
CI. TestClient hiện có một cảnh báo deprecation từ Starlette/httpx; không có test
bị skip hoặc hạ assertion. Workflow GitHub chưa chạy từ PR vì chưa push/mở PR.

Không còn lỗi P0/P1 đã biết sau các kiểm tra trên. Giữ ranh giới mạng nội bộ,
phone identity do backend tin cậy cung cấp, frozen clock và lịch sử raw theo các
lần quan sát. Host/TLS và thông tin runtime của PostgreSQL thực tế vẫn cần cấu hình
khi triển khai. Không thay đổi dữ liệu PostgreSQL của người dùng trong quá trình này.
