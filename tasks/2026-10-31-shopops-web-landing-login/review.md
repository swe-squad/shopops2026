# Review: ShopOps landing và login

Ngày: 2026-10-31. Branch: `feat/shopops-web-landing-login`.
Người dùng yêu cầu nội dung giao diện tiếng Anh và tạo PR vào `develop`.

## Kết quả review

Không còn phát hiện cần chặn PR sau các sửa chữa dưới đây. Phạm vi: correctness, readability, architecture, security và performance; tự review diff và tests, không review bằng agent phụ.

- **Đã sửa — tràn ngang:** ellipse trang trí bị xoay làm tăng scrollWidth ở phone/tablet/landscape. Bỏ phép xoay của ellipse; kiểm tra lại kích thước thật và ảnh chụp.
- **Đã sửa — deep link sau login:** snapshot mailbox cũ có thể ghi đè query/hash của trang người dùng muốn mở. Snapshot đầu bây giờ chỉ làm baseline; events mới tiếp tục được nhận. Test tạo sẵn link cũ trước login để tránh phụ thuộc thứ tự test.
- **Đã sửa — query hợp lệ:** giữ query có khoảng trắng được percent-encode; vẫn chặn ký tự điều khiển, backslash, URL ngoài và đường dẫn không thuộc shop.
- Route guard không thay auth ở backend. Token chỉ ở React memory, gửi qua Bearer header đến operations API; API mock không nhận token. Không thêm dependency, migration, biến môi trường hoặc cấu hình deploy.
- Request login có loading/error/retry và cleanup; request đã hủy không gọi callback tạo phiên. Workspace và polling chỉ mount khi có token được API xác nhận.
- Không phát sinh app state trong viewer/chat. CSS công khai không thay scroll owner của workspace. Bỏ các style bị chính thay đổi này làm mồ côi.
- Có một read incidents bổ sung khi login để xác thực theo endpoint sẵn có (API giới hạn 100 records); không polling trước login, không thêm framework/router.

## Bằng chứng

- `make -C services/shopops-web ci`: pass; 61 tests trong 12 files, lint sạch và production build thành công.
- `node scripts/sync-brand-assets.mjs --check`: pass cho 3 clients.
- `npm ci` audit: 0 vulnerabilities; không đổi manifest/lockfile. npm hiện cảnh báo phiên bản Node host hơi cũ so với range hỗ trợ của npm; các checks vẫn hoàn tất.
- `npm --prefix tests/workspace test`: 19/19 pass trên bản tiếng Anh và mailbox baseline.
- Sau tinh chỉnh giữ encoded-space query, chạy lại suite landing/login: `npm --prefix tests/workspace test -- specs/landing-login.spec.ts`: 5/5 pass.
- Mutation check: đảo điều kiện kiểm tra đường dẫn shop làm 7 tests fail. Khôi phục file rồi chạy lại guard tests thành công; final CI cũng pass.
- Test Stop response của chat timeout một lần ở lượt đầu; giữ nguyên mã/test hành vi đó, chạy riêng thành công rồi full suite thành công. Không bỏ assertion hoặc tăng timeout để che lỗi.
- Đã xem ảnh landing desktop, mobile và login mobile; tests bao phủ 1440×900, 768×1024, 390×844, 844×390 cùng các viewport viewer hiện có.

## Ảnh giao diện

- [Landing desktop](screenshots/landing-1440.png)
- [Landing mobile](screenshots/landing-390.png)
- [Login mobile](screenshots/login-390.png)

## Giới hạn

Chưa deploy thay đổi lên CapRover; đây là PR để review. Kiểm tra HTTP/bundle bản dev trước triển khai chỉ xác nhận bản hiện hành. Workspace token dùng chung vẫn là access model hiện tại; không triển khai tài khoản, cách ly theo người dùng, hosted team provisioning hoặc MCP. Token không tồn tại sau reload và chat đăng nhập độc lập.
