# Spec: Connector mock Shopee/TikTok lưu RAM trong shopops-web

## Status

Approved for autonomous implementation by the user on 2026-10-31 (`incremental-implementation auto`). API mock và state trong RAM của `shopops-web-dev`; triển khai từng increment, commit và mở PR vào develop theo yêu cầu.

## Objective

Sau khi vào workspace trên `shopops-web-dev`, người dùng có thể bấm đăng nhập
Shopee hoặc TikTok và thấy trang mock kết nối thành công. Frontend gọi API mock
ngay trong service `shopops-web` để đọc hoặc ghi trạng thái kết nối.

**Phạm vi đã chốt:** API mock + UI, state chỉ trong RAM của service. Không có
OAuth thật, dữ liệu shop thật, localStorage, database hoặc thay đổi `shopops-api`.
Đăng nhập lại vẫn thấy thành công trong cùng vòng đời process; restart/redeploy
process mock thì cả hai nền tảng trở về chưa kết nối.

## Current Behavior and Assumptions

- App hiện có bước **Unlock workspace** bằng access token. Trong scope này, đó là
  điểm vào luồng sau đăng nhập; không tạo thêm đăng nhập tài khoản ShopOps.
- `App.tsx` nhận token không rỗng để mở UI; API operations vẫn xác thực riêng.
  Mock success không phải bằng chứng token hợp lệ hoặc quyền truy cập dữ liệu thật.
- Container hiện chỉ có nginx phục vụ React static; Node 24 chỉ nằm ở build stage.
  Cần bổ sung runtime nhỏ trong cùng service để xử lý HTTP và giữ state trong RAM.
- Giữ nginx và proxy operations hiện có. API mock được nginx chuyển tới runtime
  nội bộ trong cùng container; không tạo service CapRover mới.
- Đề xuất dùng Node HTTP có sẵn, không thêm framework. Cơ chế khởi động/dừng
  runtime cùng nginx sẽ được chốt và kiểm tra ở phase Plan/Implement.
- State gồm đúng hai cờ Shopee/TikTok, dùng chung cho mọi browser truy cập một
  instance demo. Không có tài khoản, phân quyền theo user hay trạng thái riêng
  từng workspace/token trong API mock.
- Chạy một instance/process giữ state. Nhiều replica có RAM độc lập và không nằm
  trong scope; không hứa giữ trạng thái qua restart, crash hoặc redeploy.
- Các route UI dùng browser nội bộ sẵn có trên cùng origin; không redirect ra sàn.

## User Flow

1. Unlock từ trang gốc mở `/shop/connections`. Nếu đã mở deep link `/shop/...`
   cụ thể, giữ đích đó. Thêm mục Connections vào hàng điều hướng shop hiện có.
2. Màn hình Connections gọi GET API mock và hiển thị hai thẻ Shopee, TikTok với
   trạng thái riêng. Trong lúc chờ có `Checking connection…`; API trả false thì
   hiện `Not connected`, true thì hiện `Connected`. Luôn có nhãn `Demo`.
3. Bấm `Log in to Shopee` hoặc `Log in to TikTok` gọi API connect tương ứng;
   vô hiệu hóa nút đang xử lý. API ghi cờ true trong RAM và trả thành công.
4. Chỉ sau response thành công, frontend chuyển tới
   `/shop/connections/shopee/success` hoặc `/shop/connections/tiktok/success`,
   hiển thị `Connection successful`, tên nền tảng, nhãn Demo và nút
   `Back to connections`. Không có form mật khẩu sàn hoặc thời gian chờ giả.
5. Quay về danh sách thấy nền tảng đó đã connected; nền tảng còn lại giữ trạng thái
   riêng. Nút ở thẻ connected có thể mở lại trang success, không bắt kết nối lại.
6. Refresh hoặc lock rồi unlock lại sẽ GET trạng thái từ process mock và vẫn thấy
   connected nếu process chưa restart. Browser khác cũng đọc được state đó.
7. Overview/Incidents truy cập được trước và sau kết nối. Có đường tới Overview
   để bỏ qua flow. Tab nội bộ mới vẫn mở Overview như hiện tại.
8. Mở trực tiếp success URL không ghi state: kiểm tra GET trước. Nếu chưa kết nối,
   hiện lời nhắc về Connections; platform/path lạ dùng trang không khả dụng.

## Mock API Contract

Endpoint nằm trong `shopops-web`, browser gọi đường dẫn tương đối cùng origin:

| Method / path | Hành vi |
| --- | --- |
| `GET /api/mock/connectors` | HTTP 200, `{connections: [{platform: "shopee", connected: false, mock: true}, {platform: "tiktok", connected: false, mock: true}]}` ở trạng thái ban đầu; các cờ phản ánh RAM hiện tại. |
| `PUT /api/mock/connectors/{platform}` | Không cần body; đặt `connected: true` cho `shopee` hoặc `tiktok`; HTTP 200 trả `{platform, connected: true, mock: true}`. Gọi lặp vẫn thành công, không tạo thêm state. |

- Handler chỉ chứa state demo không nhạy cảm, không nhận/gửi workspace token và
  không gọi backend hoặc sàn. API demo dùng chung không phải API xác thực user;
  không dùng state này để mở quyền đọc/ghi operations thật.
- Platform ngoài danh sách trả 400; path không có trả 404; method không hỗ trợ trả
  405. Response JSON có `Cache-Control: no-store`, không trả trang HTML fallback.
- Không mở CORS cho website khác; mutation chỉ chấp nhận request browser cùng
  origin (kiểm tra Origin nếu có); request không có Origin vẫn dùng được từ công
  cụ kiểm tra trực tiếp. Đây là demo công khai, không có claim bảo mật user.
- Không lưu token, cookie, account, shop ID, mật khẩu hoặc dữ liệu cá nhân.
- State khởi tạo false khi process bắt đầu, nằm ngoài vòng đời từng HTTP request.
  Reload UI, lock, đổi token hoặc đóng tab không reset server state.
- Giữ một nguồn state trong process; không dùng các worker độc lập cho mock.
  Không thêm endpoint reset/disconnect; restart process là cách reset bản demo.
- Cùng logic handler/state được dùng ở local dev và runtime container; từng process
  có state riêng. API mock local phải hoạt động qua cổng Vite hiện có.

## UI and State Rules

- React giữ bản state để render trong memory; không persist localStorage,
  sessionStorage hoặc IndexedDB. Server mock là nguồn trạng thái chính.
- GET lại khi unlock, mở Connections hoặc mở success page; tab nội bộ đang hoạt
  động phản ánh kết quả mới. Không yêu cầu đồng bộ realtime giữa browser khác nhau.
- Loading, saving, error và Retry rõ ràng. Lỗi GET không bị coi là chưa kết nối;
  lỗi PUT không được chuyển sang trang thành công. Request timeout hữu hạn,
  có AbortSignal; bỏ qua response cũ sau lock/unmount.
- Có thể retry PUT vì thao tác idempotent. Nếu response bị mất, GET lại sẽ cho
  biết cờ đã được ghi hay chưa.
- Giữ token chỉ trong memory theo app hiện tại; lock vẫn hủy request operations
  và navigation, không làm mất RAM của process mock.
- State dùng chung giữa các tab nội bộ nhưng giữ history/draft/scroll riêng.
  Không remount panel không hoạt động hoặc làm thay đổi navigation mailbox.
- Theo canonical brand: `--shopops-*`, ivory, white, charcoal, action orange,
  Inter/system. Nhãn/icon trạng thái rõ, focus bàn phím, vùng bấm tối thiểu 44px.
- `.shop-page` sở hữu scroll, header/toolbar/tab strip nằm trong viewport; kiểm tra
  phone, tablet, desktop, short landscape và viewer nhúng.
- Success có nhãn Demo và nội dung ngắn nói chưa đồng bộ dữ liệu cửa hàng. Giữ
  thông báo dữ liệu thật chưa kết nối và incidents nhập thủ công.

## Tech Stack

Theo manifests và Dockerfile hiện có:

- React/React DOM `^19.3.1`, TypeScript `~6.0.3`, Vite `^8.3.4`.
- Vitest `^5.0.5`, Testing Library React `^16.3.3`, jsdom `^29.1.1`.
- oxlint `^1.88.0`; Node 24 Alpine build stage, nginx 1.29 Alpine runtime hiện tại.
- Đề xuất bổ sung Node runtime cùng service cho HTTP mock, dùng standard library;
  không thêm npm framework/router/dependency. Giữ frontend container port 80.
- Phiên bản package trên là khai báo manifest; cài đặt thực tế dùng lockfile.

## Commands

Lệnh hiện có, chạy từ repo root:

```sh
npm --prefix services/shopops-web ci
npm --prefix services/shopops-web run dev -- --port 5173 --strictPort
npm --prefix services/shopops-web run lint
npm --prefix services/shopops-web test
npm --prefix services/shopops-web run build
make -C services/shopops-web ci
make -C services/shopops-web docker
node scripts/sync-brand-assets.mjs --check
```

Browser regression theo `tests/workspace/README.md`, sau khi cài dependencies của
các service liên quan:

```sh
npm --prefix tests/workspace ci
cd tests/workspace
npx playwright install chromium
npm test
```

Lệnh runtime mock mới và container smoke test cụ thể được ghi vào Plan/README
khi chốt runtime. Không chạy test implementation ở phase viết spec.

## Project Structure

- `services/shopops-web/src/App.tsx`: unlock/lock và vòng đời UI.
- `src/browser-pane.tsx`, `src/browser-tabs.ts`: điều hướng, initial page, tiêu đề tab.
- `src/shop-client.tsx`, `src/index.css`: shop pages, navigation và styles.
- Component/state connector và test `*.test.ts(x)` đặt cạnh source trong `src/`.
- Handler HTTP/state mock và runtime entrypoint mới đặt dưới `services/shopops-web/`,
  tách khỏi browser bundle; tên file cụ thể được chốt ở Plan.
- `vite.config.ts`: gắn mock handler local dev.
- `Dockerfile`, `nginx.conf`, startup scripts: runtime mock trong cùng container,
  route `/api/mock/`, kiểm tra lifecycle process và giữ proxy operations hiện có.
- `README.md`, `AGENTS.md`: cập nhật service có mock runtime và vòng đời RAM.
- `tests/workspace/specs/`: browser regression cho flow/layout hiện có và connector.
- `tasks/2026-10-31-mock-marketplace-connectors/`: toàn bộ artifact task.

## Code Style

React function components/hooks, typed props, relative imports, single quotes,
không semicolon; ví dụ thực tế từ `src/App.tsx`:

```tsx
function BrowserSession({ token }: { token: string }) {
  const navigation = useNavigationRequests(token)
  return <main className="workspace-main standalone-browser">
    {navigation.error && <p className="navigation-warning" role="status">{navigation.error}</p>}
    <BrowserPane token={token} requestedUrl={navigation.request} />
  </main>
}
```

Platform giới hạn `shopee | tiktok`. Mock handler nhỏ, state rõ ràng, không tạo
framework/adapter không cần thiết. Test UI query theo role/label như AGENTS.md.

## Testing Strategy

- Vitest/Testing Library: unlock tới Connections, GET loading/error/retry, từng
  nút connect gọi đúng API, PUT thành công mới điều hướng, independent platform
  state, quay lại và lock/unlock đọc lại server, không persist browser storage.
- Handler tests dùng instance state độc lập: default false, GET/PUT, idempotency,
  invalid platform/path/method/origin, no-store; nhiều request đọc cùng state,
  instance process mới trở về false.
- Test abort/response cũ không cập nhật phiên mới; success URL không tự ghi state;
  mock không mang bearer token, không thay đổi authorization của operations.
- Browser regression: luồng connector với mock HTTP thật, refresh/đăng nhập lại,
  browser context khác đọc cùng state; giữ incidents, navigation, history/drafts,
  tab keyboard controls và layout standalone/embedded.
- Container smoke test bắt buộc vì runtime thay đổi: image build; port 80, health,
  SPA fallback, assets, CSP và proxy operations vẫn hoạt động; GET/PUT mock giữ
  state qua nhiều request; restart reset; process shutdown không để mock chết
  âm thầm trong container vẫn được báo healthy. Chốt cách kiểm tra ở Plan.
- Không đặt ngưỡng phần trăm coverage mới. Chạy service CI, brand drift và browser
  regression liên quan; test local không chứng minh đã deploy trên dev.

## Boundaries

- **Always:** Chỉ mock state trong RAM của `shopops-web`; API/UI cùng contract;
  validate platform/path/method; label Demo; giữ operations auth/proxy; tests đi
  cùng thay đổi hành vi; kiểm tra Docker/runtime lifecycle; cập nhật docs.
- **Ask first:** OAuth hoặc dữ liệu thật; persistence database/disk/browser storage;
  tách service mới; thêm dependency; user identity/auth; thay đổi service khác,
  workflow CI hoặc mở rộng production.
- **Never:** Commit secret, thu thập credential sàn, coi state mock là quyền truy
  cập thật, gửi token tới mock hoặc sàn, bỏ failing test để vượt check.

Thay đổi Docker/nginx/startup trong `shopops-web` cần thiết để chạy API RAM nằm
trong phạm vi spec này. Không thay đổi `shopops-api`, DB, agent contracts hoặc
đăng ký service mới. Đích demo là dev; spec không tự thực hiện deploy.

## Success Criteria

1. Sau unlock, người dùng mở Connections và thấy đúng trạng thái GET của hai sàn.
2. Bấm login gọi PUT; API cập nhật RAM và UI chuyển tới đúng success page.
3. Hai sàn độc lập; kết nối lại idempotent; status luôn có nhãn Demo.
4. Refresh, đóng/mở browser và lock/unlock vẫn đọc được success khi process sống.
5. Restart process/container hoặc redeploy reset cả hai trạng thái về false.
6. Browser khác đọc chung state của cùng instance; không có lưu riêng theo user.
7. Không DB, localStorage/sessionStorage, OAuth thật hoặc thay đổi shopops-api.
8. Errors không hiện success giả; URL success trực tiếp không tự connect.
9. Operations, proxy, viewport và navigation tiếp tục hoạt động; checks liên quan
   và container smoke test pass khi triển khai.

## Open Questions

Không còn câu hỏi chức năng bắt buộc. Giả định: dùng Unlock workspace hiện có,
state demo dùng chung trong một process service, và nhãn Demo trên UI.

User đã cho phép tự triển khai, không yêu cầu duyệt lại từng phase. Commit/push và mở PR vào develop sau khi kiểm tra.
