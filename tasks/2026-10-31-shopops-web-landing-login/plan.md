# Implementation plan: landing và login ShopOps

Người dùng cho phép tự động triển khai ngày 2026-10-31. Giữ auth Bearer token, API và hạ tầng hiện tại. Không thêm dependency.

## Các phần thực hiện

1. **Form kiểm tra token (M, không phụ thuộc):** thêm `src/login-page.tsx` và test. Chấp nhận khi token được API xác nhận, lỗi và request bị hủy không tạo phiên. Kiểm tra: `npm --prefix services/shopops-web test` và `npm --prefix services/shopops-web run build`.
2. **Route công khai và protected workspace (M, sau 1):** sửa `App.tsx`, thêm helper route/test, cập nhật `App.test.tsx`. Chấp nhận khi landing/login/shop riêng, quay lại deep link an toàn, lock/back/reload đúng. Cùng lệnh test/build bước 1. Checkpoint: core flow hoạt động, stage đúng files.
3. **Landing và giao diện login (M, sau 2):** component landing, CSS, metadata và test. Dùng logo/tokens đã vendor, minh họa HTML/CSS để không thêm asset/tooling. Chấp nhận khi tiếng Anh, responsive, CTA hoạt động, nội dung phản ánh tính năng thật. Cùng lệnh test/build bước 1.
4. **Browser regression và tài liệu (M, sau 3):** cập nhật helpers/specs tại `tests/workspace`, thêm landing/login scenarios và README service. Chấp nhận khi cả standalone và embedded viewer đi qua login, giữ các regression cũ. Kiểm tra `npm --prefix tests/workspace test`, `make -C services/shopops-web ci`, `node scripts/sync-brand-assets.mjs --check`.
5. **Giữ đích login trước mailbox cũ (sau 4):** kiểm tra thực tế phát hiện snapshot navigation cũ ghi đè deep link; thay snapshot đầu thành baseline và test sự kiện mới vẫn được xử lý. Files: `use-navigation-requests.ts`, `App.test.tsx`, README. Xác minh service tests/build và browser regression.
6. **Review và bàn giao (sau 4):** review correctness/security/architecture/readability/performance, mutation check cho redirect guard; ghi bằng chứng vào review.md, hoàn thành todo. Stage files riêng theo từng slice; commit tại checkpoint cuối, không tự merge.

## Rủi ro và giới hạn

- URL `next` không tin cậy: chỉ cho đường dẫn /shop cùng origin; không chuyển sang web ngoài.
- Token: giữ trong React state, chỉ gửi tới operations API; không đưa vào storage/URL/log.
- Request login hoàn tất sau khi rời form: abort + kiểm tra signal trước callback.
- Global overflow/viewer: giữ document fixed viewport, landing/login có scroll owner riêng.
- Thay route làm thay hành trình test: cập nhật helper nhưng giữ assertion workspace/chat/connector.
- Live deploy phụ thuộc quyền GitHub/CapRover; báo rõ nếu chỉ xác minh local. Không coi offline tests là bằng chứng hosted agent/MCP.
