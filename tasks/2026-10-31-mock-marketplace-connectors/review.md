# Review

Đã rà correctness, readability, architecture, security và performance theo spec.

- API chỉ giữ hai cờ demo công khai trong một process; không nhận token, không gọi sàn hoặc operations. GET/PUT có no-store, allowlist platform/method/path và kiểm tra Origin.
- UI chờ API thành công, có timeout/error/retry, bỏ response cũ, không persist dữ liệu trên browser. Draft incidents, tab history và keyboard focus được kiểm tra.
- Runtime khởi động nginx sau khi mock listener sẵn sàng; lỗi child hoặc listener kết thúc runtime; SIGTERM dừng cả hai. Vite dùng cùng handler.
- Không thêm dependency npm, env hoặc volume. npm ci audit: 0 vulnerabilities.
- Đã sửa lỗi type trong test và tách route helper khỏi React component để lint sạch.
- Mutation check: đổi cờ PUT thành false làm 2 test API fail như mong đợi; đã khôi phục code trước checks cuối.

## Verification

- `rtk proxy make ci` trong `services/shopops-web`: lint sạch, 33 tests pass, TypeScript/Vite build pass.
- `npm test` trong `tests/workspace`: 14 tests pass; flow connect/relogin/reload/browser khác, viewport 375/768/1280/1440 và short landscape.
- Đã xem ảnh desktop/mobile từ Playwright; viewport, controls và scroll đúng.
- `node scripts/sync-brand-assets.mjs --check`: pass cho cả 3 clients.
- `git diff --check`: pass.
- Rebase lên `origin/develop` (`6389cef`) không conflict; chạy lại toàn bộ 14 browser tests trên baseline mới: pass.
- Node runtime import được ngoài package.json, tương ứng layout file trong container.

## Giới hạn còn lại

Docker build không chạy được do Docker daemon/socket không có; sudo không chạy noninteractive. Tests runtime dùng Node child thay thế nginx để kiểm tra supervisor, không thay cho việc kiểm tra image/nginx thật. Container build và smoke test triển khai vẫn cần môi trường có Docker. Không có claim đã deploy hoặc kết nối sàn thật.
