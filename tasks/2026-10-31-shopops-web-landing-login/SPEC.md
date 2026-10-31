# Spec: ShopOps landing page và trang đăng nhập riêng

Trạng thái: Đã được người dùng cho phép tự động triển khai qua yêu cầu “incremental-implementation auto” ngày 2026-10-31.
Ngày: 2026-10-31 (Asia/Ho_Chi_Minh).
Service: `services/shopops-web`.

## Objective

Tách phần giới thiệu công khai và đăng nhập khỏi màn hình làm việc ShopOps để người bán hiểu sản phẩm trước khi truy cập workspace.

Người dùng đã xác nhận: **giữ workspace token; đăng nhập xong vào màn hình ShopOps hiện tại**. Không bổ sung tài khoản email/mật khẩu hoặc đăng ký.

Các giả định thiết kế để duyệt:

- `/` là landing page công khai; `/login` là trang đăng nhập riêng.
- “Trang chính” sau đăng nhập là workspace hiện tại, mặc định mở `/shop/connections` theo hành vi đang có. Các tab mới vẫn mở Overview.
- Nội dung mới trên landing/login dùng tiếng Anh theo yêu cầu bổ sung của người dùng; không dịch toàn bộ workspace trong thay đổi này.
- Giữ React/Vite, cơ chế token chỉ trong bộ nhớ và bộ nhận diện ShopOps hiện có.

## Current State and Evidence

- `src/App.tsx` hiện đặt phần giới thiệu và form “Open your shop browser” trên cùng màn hình. Submit chỉ trim rồi lưu token vào React state; chưa kiểm tra API trước khi mở workspace.
- `src/browser-tabs.ts` mở Connections khi vào từ root, giữ đường dẫn `/shop/...` khi truy cập trực tiếp, và mở Overview cho tab mới.
- `shopops-api` xác thực Bearer token cho `/api/operations/*`; thiếu hoặc sai token trả 401. Không có luồng đăng nhập tài khoản trong client này.
- `nginx.conf` đã có SPA fallback và proxy `/api/operations/` qua runtime `API_URL`; không cần thay đổi deploy để thêm route phía client.
- Kiểm tra HTTP ngày 2026-10-31: `https://shopops-web-dev.cr.ngochoanielts.com/`, `/login`, `/shop/connections` đều trả HTML 200. Bundle đang deploy chứa form unlock và route Connections. Đây là bằng chứng HTTP/bundle, chưa phải kiểm tra tương tác bằng trình duyệt; 200 tại `/login` hiện chỉ là SPA fallback.
- API incidents trên dev trả 401 khi không gửi token. Chưa kiểm tra đăng nhập thành công với token thật.
- Link CapRover của người dùng trả shell dashboard; chưa có phiên quản trị để kiểm tra cấu hình app, log hoặc revision deploy. Không thay đổi cấu hình CapRover trong giai đoạn đặc tả.
- Đã đối chiếu `docs/agent-integration.md` và `docs/system-architecture.md`: token dùng chung hiện tại chưa đáp ứng định danh và cách ly theo người dùng của kiến trúc đích. Tách landing/login không giải quyết đăng ký, provisioning team, hosted runtime hoặc MCP; không tuyên bố các phần đó đã hoàn thành.

## Experience and Routing

### Landing page

- Header có logo ShopOps, liên kết đến phần cách hoạt động và CTA “Log in”.
- Hero dùng headline “Clarity in the chaos.”, mô tả ngắn dành cho người bán và CTA đi đến `/login`.
- Phần giới thiệu nêu đúng khả năng hiện có: xem/ghi nhận sự cố, giữ các trang công việc trong tab, trải nghiệm kết nối sàn mô phỏng. Không quảng cáo đồng bộ Shopee/TikTok thật hay tự động xử lý đã hoàn thiện.
- Có phần cách sử dụng ngắn: mở workspace bằng token → xem kết nối/sự cố → chọn việc cần xử lý; CTA cuối trang dẫn đến login.
- Dùng brand assets sẵn có và bố cục đồ họa bằng HTML/CSS khi phù hợp. Hình minh họa mang tính ý tưởng phải được nhận diện là minh họa, không giả thành dữ liệu thật hoặc ảnh chụp tính năng đã triển khai.
- Không thêm testimonial, số liệu hiệu quả, bảng giá, form thu thập email hoặc CTA không hoạt động.
- Khi đã có phiên trong bộ nhớ, CTA chuyển thành “Open workspace” và mở workspace mà không yêu cầu nhập lại token.

### Login and access

- `/login` có logo, tiêu đề “Log in to ShopOps”, trường mật khẩu được gắn nhãn rõ “Workspace access token”, nút “Log in” và liên kết “Back to home”.
- Nêu rõ token chỉ lưu trong bộ nhớ; tải lại trang cần nhập lại. Chat vẫn đăng nhập độc lập.
- Trim token; chặn giá trị rỗng/toàn khoảng trắng. Không nhận email/mật khẩu của sàn.
- Khi submit, kiểm tra token bằng `GET /api/operations/incidents` với Bearer header và `cache: 'no-store'`. Đây là endpoint đọc đã có, không thêm endpoint hoặc schema; dữ liệu trả về không hiển thị trên login.
- Chỉ tạo phiên phía client và chuyển trang sau response thành công. Hiển thị trạng thái đang kiểm tra và chặn submit lặp.
- 401: báo token không hợp lệ ngay trên form. Lỗi mạng/5xx: báo không thể kết nối và cho thử lại. Không đánh đồng sự cố server với token sai.
- Hủy request khi rời login/unmount; response cũ không được tạo phiên hoặc chuyển trang. Xóa draft token khi đăng nhập thành công hoặc rời form.
- Không gửi token qua URL, browser storage, log, iframe, cookie tự tạo hoặc API mock connector.

### Route behavior

| Tình huống | Kết quả |
| --- | --- |
| Mở `/` khi chưa đăng nhập | Landing, không mount workspace hoặc gọi API operations |
| Chọn CTA đăng nhập | Mở `/login` trong cùng SPA |
| Đăng nhập hợp lệ từ landing/login | Mở `/shop/connections` |
| Mở trực tiếp `/shop/...` khi chưa có phiên | Chuyển đến login, lưu đích nội bộ hợp lệ; đăng nhập xong quay lại đích đó |
| Mở `/login` khi đã có phiên | Chuyển đến đích nội bộ hợp lệ hoặc Connections |
| Về `/` khi đang có phiên | Hiển thị landing và CTA vào workspace; không làm mất token do reload ngoài ý muốn |
| Lock workspace | Xóa token/draft, unmount workspace và hủy request/polling; về `/login` với mặc định Connections |
| Reload một route workspace | Token mất theo thiết kế hiện tại; về login và giữ đích nội bộ để quay lại |
| Back/Forward của trình duyệt | UI theo route, không vượt access guard hoặc tạo vòng lặp redirect |
| Đường dẫn ngoài `/`, `/login`, `/shop` và `/shop/*` | Hiển thị trạng thái không tìm thấy và liên kết về landing; không coi là workspace |

Đích quay lại chỉ được là đường dẫn shop cùng origin (`/shop` hoặc `/shop/...`), bảo toàn query/hash hợp lệ. Nếu dùng query `next`, phải chuẩn hóa và kiểm tra trước khi điều hướng; từ chối URL ngoài origin, `//host`, credentials, backslash, ký tự điều khiển và scheme như `javascript:`. Đích sai dùng Connections. Không áp dụng bộ kiểm tra URL preview bên trong workspace như thể mọi HTTP(S) URL đều là đích login hợp lệ.

Điều hướng giữa các trang cùng ứng dụng không reload document làm mất token. Khi mở workspace, snapshot mailbox đầu tiên chỉ thiết lập mốc sự kiện đã tồn tại; không phát lại link chat cũ để ghi đè đích login. Các sự kiện mới sau mốc này vẫn mở trong tab đang chọn.

History của các tab trong workspace tiếp tục độc lập với route cấp ứng dụng; không yêu cầu đồng bộ mọi thao tác tab lên thanh địa chỉ trình duyệt thật.

## Tech Stack

Theo `services/shopops-web/package.json` (range khai báo, không phải cam kết phiên bản resolve):

- React / React DOM `^19.3.1`, TypeScript `~6.0.3`, Vite `^8.3.4`.
- Vitest `^5.0.5`, Testing Library React `^16.3.3`, jsdom `^29.1.1`, oxlint `^1.88.0`.
- Browser regression: Playwright `1.64.1` trong `tests/workspace`.
- Nginx phục vụ SPA ở port 80; API same-origin. Không có router dependency; ưu tiên cơ chế route nhỏ dùng History API và React, không thêm thư viện chỉ để tách ba nhóm trang.

## Commands

Chạy từ repository root, lấy từ Makefile/package manifests/README đang có:

```sh
# Cài dependencies và chạy riêng service
npm --prefix services/shopops-web ci
npm --prefix services/shopops-web run dev -- --port 5173 --strictPort
npm --prefix services/shopops-web test
npm --prefix services/shopops-web run lint
npm --prefix services/shopops-web run build

# Kiểm tra đầy đủ theo CI service (install + lint + test + build)
make -C services/shopops-web ci

# Brand assets
node scripts/sync-brand-assets.mjs --check
# Chỉ chạy nếu thay đổi canonical assets hoặc danh sách vendor:
node scripts/sync-brand-assets.mjs

# Chuẩn bị browser regression theo tests/workspace/README.md
npm --prefix services/shopops-chat ci
npm --prefix services/shopops-workspace ci
make -C services/shopops-api install
make -C services/shopops-chat-api install
npm --prefix tests/workspace ci
(cd tests/workspace && npx playwright install chromium)
npm --prefix tests/workspace test
```

Playwright tự khởi động 5 services ở các port 8000, 8001, 5173, 5174, 5175; không tái sử dụng server đang chạy. Không dừng tiến trình không thuộc tác vụ. Không chạy checks triển khai trong lượt chỉ viết đặc tả.

## Project Structure

- `services/shopops-web/src/App.tsx`: hiện sở hữu token và mount workspace; nơi tích hợp route/access flow.
- `src/browser-pane.tsx`, `browser-tabs.ts`, `shop-client.tsx`: workspace hiện tại, tab và trang shop cần giữ hành vi.
- `src/workspace-api.ts`: Bearer header và xử lý response dùng chung.
- `src/index.css`, `index.html`, `public/brand/`: styles, metadata và bản vendor của assets.
- `src/*.test.ts(x)`, `src/test/setup.ts`, `mock/*.test.ts`: tests service.
- `tests/workspace/specs/`: browser regression; helper unlock và tests hiện giả định form nằm ngay tại root, phải cập nhật theo hành trình landing → login.
- `docs/brand/{design-guidelines,brand-direction,landing-page-copy}.md`: nguồn thiết kế và nội dung. Copy landing là bản đề xuất, cần đối chiếu khả năng thật.
- `scripts/sync-brand-assets.mjs`: nơi đồng bộ asset canonical; không sửa bản generated bằng tay. Nếu dùng thêm hero/logo, mở rộng đồng bộ có kiểm soát và kiểm tra drift các client liên quan.
- `services/shopops-web/README.md`: cập nhật đường dẫn, hành trình login, validation và giới hạn phiên.
- `tasks/2026-10-31-shopops-web-landing-login/`: toàn bộ artifact của tác vụ; bao gồm đặc tả, kế hoạch, checklist và kết quả review.

## Code Style

Giữ function components/hooks, TypeScript, named exports cho helper, nháy đơn và style không dấu chấm phẩy như mã hiện tại. Ví dụ có thật trong `src/workspace-api.ts`:

```ts
export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}
```

Tách trách nhiệm landing, form login và route/access rõ ràng; không xây framework auth tổng quát. Dùng role/label trong test, không selector CSS/test id nếu có ngữ nghĩa phù hợp.

Thiết kế theo **Clarity in the chaos**: nền ivory, surface trắng, chữ charcoal, accent cam có tiết chế, token `--shopops-*`, Inter/system. Nút dùng action orange đủ tương phản. Mục tiêu chạm tối thiểu 44px, focus rõ, form có label, lỗi có text và alert, hỗ trợ reduced motion.

Giữ document/browser chrome trong viewport theo AGENTS service. Landing/login có vùng cuộn nội dung riêng; workspace tiếp tục để `.shop-page` sở hữu cuộn dọc. Không tạo overflow ngang hoặc thay global overflow làm vỡ viewer. Cập nhật title/ngôn ngữ phù hợp trang mới mà không gán sai ngôn ngữ cho toàn workspace tiếng Anh.

## Testing Strategy

- Vitest + Testing Library: landing không chứa token form; CTA chuyển đúng trang; submit rỗng/loading/success/401/network/5xx; hủy request khi rời trang; không tạo phiên từ response đã hết hiệu lực.
- Route/access tests: default Connections, deep link và hash/query hợp lệ, từ chối redirect ngoài phạm vi, browser Back/Forward, `/login` khi đã có phiên, lock và reload, unknown route.
- Token không xuất hiện trong URL/storage; không mount polling hoặc tải operations trước khi submit login. Sau lock, các request đang chạy phải abort và nội dung workspace không còn truy cập qua Back.
- Giữ regression tab history/draft, keyboard navigation, mailbox từ chat, incidents và mock connector. Login không đổi trạng thái mock hoặc dùng mock để xác thực.
- Playwright chạy hành trình landing → login → workspace và xác thực sai với API fixture thật của suite; cập nhật helper theo UI mới, giữ chat unlock độc lập và kiểm tra viewer.
- Kiểm tra desktop 1440×900, tablet 768×1024, phone 390×844 và landscape 844×390: không tràn ngang, nội dung cuộn đúng vùng, CTA/form dùng được bằng keyboard; tab workspace vẫn giữ draft khi đổi tab.
- Không có ngưỡng coverage số được khai báo cho service; yêu cầu phủ các nhánh hành vi thay đổi, không tự đặt phần trăm.
- Sau triển khai chạy `make -C services/shopops-web ci`, brand drift check và workspace suite. Báo rõ checks chưa chạy hoặc hạn chế môi trường. Tests offline không chứng minh deploy CapRover hay provisioning/MCP live.
- Sau khi có bản deploy dev trong giai đoạn thực thi, kiểm tra trực tiếp `/`, `/login`, deep link và login hợp lệ nếu có token được cấp; không ghi token vào artifact.

## Boundaries

- **Always:** làm trên feature branch; giữ API same-origin và `API_URL` nội bộ; xác thực ở API; giữ token trong bộ nhớ; abort I/O khi unmount; giữ app/chat/viewer độc lập; đồng bộ tests và README với hành vi mới; chạy checks trước commit; giữ dữ liệu/demo state hiện có.
- **Ask first:** thay workspace token bằng auth tài khoản; thêm dependencies, schema/backend API mới, CI/deploy/runtime env mới; đổi đích mặc định thành một dashboard khác; mở rộng sang registration/provisioning. Không cần hỏi lại các chỉnh sửa UI/tests/docs đã được đặc tả duyệt bao quát.
- **Never:** commit secrets/`.env`/`captain.json`; đưa token vào `VITE_*`, URL hoặc log; dùng mock flags làm quyền truy cập; bỏ tests lỗi để pass; bịa dữ liệu/khả năng sản phẩm; tạo thêm hosting/service ngoài CapRover cho thay đổi này.
- Lượt đặc tả không sửa mã ứng dụng, push, merge hoặc deploy.

## Success Criteria

1. Người chưa đăng nhập mở root thấy landing hoàn chỉnh, có CTA hoạt động và không thấy form token tại đây.
2. Login có URL riêng, mở trực tiếp và refresh được nhờ SPA fallback.
3. Token hợp lệ được API xác nhận rồi chuyển vào Connections; token sai ở lại login với lỗi rõ ràng.
4. Deep link shop quay lại đúng đích sau login; đích không an toàn không được mở.
5. Lock xóa phiên; reload yêu cầu nhập lại; Back/Forward không bỏ qua guard hoặc làm lặp chuyển trang.
6. Workspace, tab drafts/history, incidents, mock connectors, chat navigation và viewer tiếp tục hoạt động theo tests hiện có.
7. Các viewport, keyboard/focus, scrolling và brand constraints đạt checks mô tả ở trên.
8. Service CI, brand drift check và browser regression pass; mọi giới hạn live verification được báo rõ.

## Open Questions

Không còn câu hỏi bắt buộc về loại đăng nhập: người dùng đã xác nhận giữ token và vào workspace hiện tại. Người dùng đã cho phép tự động triển khai, gồm tiếng Anh cho trang mới (đã được người dùng yêu cầu) và Connections làm đích mặc định. Nếu cần thay đổi hai lựa chọn đó, cập nhật đặc tả trước khi lập kế hoạch.

## Workflow Gate

Đã dừng sau đặc tả ở lượt trước. Người dùng đã yêu cầu “incremental-implementation auto” ở lượt tiếp theo; tiếp tục plan/tasks và triển khai tự động theo phạm vi đã chốt.
