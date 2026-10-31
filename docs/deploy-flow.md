# ShopOps: triển khai lên CapRover

Tài liệu này chỉ đường đến pipeline và nơi cấu hình vận hành của monorepo ShopOps. Đây không phải xác nhận rằng app, secrets, registry hay môi trường cloud đã được provision. Cấu hình từng client/API thuộc [client workspace](client-workspace.md); ranh giới runtime và phần chưa tích hợp thuộc [system architecture](system-architecture.md).

## Nguồn chuẩn

| Cần tìm | Nơi sở hữu |
| --- | --- |
| CI cho PR | [ci.yml](../.github/workflows/ci.yml) và [_ci.yml](../.github/workflows/_ci.yml) |
| Deploy sau push hoặc chạy thủ công | [deploy.yml](../.github/workflows/deploy.yml) |
| Deploy bản PR vào dev | [pr-deploy.yml](../.github/workflows/pr-deploy.yml) |
| Build image, GHCR, môi trường và deploy | [_build-deploy.yml](../.github/workflows/_build-deploy.yml) |
| Chọn service bị ảnh hưởng | [changed-services.sh](../.github/scripts/changed-services.sh) |
| Ghi cấu hình GitHub environment | [setup-service.sh](../scripts/setup-service.sh) |
| Stack, port, build args và kiểm tra từng service | `services/<service>/service.json`, `Makefile`, `Dockerfile`, `README.md` và `AGENTS.md` tương ứng |

Workflow và script là nguồn chuẩn cho trigger, tên secret, tag image và quyền GitHub. Không sao chép chúng sang một cấu hình triển khai riêng.

## Chọn đúng môi trường

Làm trên feature branch, mở PR vào `develop`. Merge vào `develop` dùng GitHub environment `codex-sea-dev`; merge vào `main` dùng `codex-sea-prod`. Chuẩn bị app và secrets production cho mọi service bị ảnh hưởng trước khi merge vào `main`: thiếu cấu hình production làm deploy thất bại, không có cơ chế tự bỏ qua service chỉ có dev.

PR cùng repository có thể dùng `/deploy` hoặc `/deploy <service> ...` để thử trên **app dev dùng chung**, không tạo preview riêng. Bản PR có thể bị thay bởi deploy dev tiếp theo. Xem điều kiện người gọi, PR đang mở và chặn fork trong [PR Deploy](../.github/workflows/pr-deploy.yml).

Khi cần deploy lại mà không đổi code, dùng Actions → **Deploy** → **Run workflow**, chọn đúng branch và danh sách service. Để danh sách trống nghĩa là chọn tất cả. Branch `main` nhắm production; branch khác nhắm dev. Lựa chọn này có thể thay thế app đang chạy, nên xác nhận branch và service trước khi chạy.

Đổi file dùng chung ngoài `services/` không tự chọn service cho CI/deploy. Nếu thay đổi chung cần kiểm tra hoặc phát hành lại service, chọn chúng một cách chủ động; xem [bộ chọn service](../.github/scripts/changed-services.sh) thay vì suy luận từ một lần chạy rỗng.

## Chuẩn bị app và quyền truy cập

Chọn repository từ Git remote của checkout đang làm việc, không dùng tên repository hoặc đường dẫn máy cá nhân trong ví dụ cũ. Tài khoản vận hành cần quyền quản lý environment/secrets của repository và app CapRover đúng môi trường; xin quyền từ chủ sở hữu khi thiếu, không đổi sang tài khoản hay app khác.

Dashboard CapRover được chỉ định trong [hướng dẫn repository](../AGENTS.md#caprover-host-and-domains). Tại **Apps**, chọn đúng app theo quy ước `<service>-dev` cho dev và `<service>` cho production. Kiểm tra tên app trước khi chỉnh cấu hình.

- Lấy container port từ `service.json` của service, rồi đặt trong **App Configs**.
- Các client public dùng HTTPS. API nội bộ bật **Do not expose as web app**, không public domain hoặc Port Mapping.
- Giao tiếp giữa app trong cluster dùng địa chỉ nội bộ và runtime env tương ứng; cấu hình ShopOps nằm ở [client workspace](client-workspace.md#development-and-deployment).
- Bật App Token riêng cho app cần deploy. Deployment token thuộc GitHub environment; runtime credentials thuộc CapRover **App Configs**. Không đưa giá trị vào repository, chat hoặc browser build args.
- Khi image GHCR cần xác thực, registry credential của CapRover phải có quyền đọc đúng package. Kiểm tra quyền package/registry trong tài khoản được phép; không giả định một tài khoản cá nhân hoặc PAT cũ còn hợp lệ.

Dùng [setup-service.sh](../scripts/setup-service.sh) để ghi cấu hình dev hoặc cả dev/production theo interface của script, từ phiên terminal đã xác thực đúng repository. Script có thể bỏ qua biến đầu vào chưa được cấp; chạy xong không chứng minh cấu hình đã đủ. Đối chiếu kết quả với bước **Check CapRover secrets** của pipeline. Không đọc lại giá trị secret để viết tài liệu hoặc báo cáo.

App dùng dữ liệu bền vững cần volume và cấu hình instance phù hợp trước khi thay container. [Client workspace](client-workspace.md#development-and-deployment) sở hữu ràng buộc lưu trữ của các backend ShopOps; image rollback không khôi phục dữ liệu.

## Kiểm tra và tìm log

Chọn đúng service, môi trường và commit khi kiểm tra một lần deploy:

1. Trong GitHub → **Actions**, mở run **CI**, **Deploy** hoặc **PR Deploy** tương ứng. Kiểm tra danh sách service được chọn, job CI và bước deploy; [_build-deploy.yml](../.github/workflows/_build-deploy.yml) là đường đi từ CI đến GHCR và CapRover.
2. Trong CapRover → **Apps** → app đích, đối chiếu image đã chọn với revision của run. Xem log app của đúng lần triển khai khi container lỗi; log Actions và log ứng dụng trả lời hai loại vấn đề khác nhau.
3. Mở client HTTPS và kiểm tra luồng cần dùng qua client, gồm API same-origin và chat streaming khi liên quan. Không mở public domain cho API nội bộ chỉ để kiểm tra.
4. Với thay đổi lưu trữ, kiểm tra dữ liệu vẫn còn sau khi thay container trong môi trường đã được phép kiểm thử.

Giới hạn log theo thời gian và lỗi cần điều tra; che dữ liệu người bán, token và thông tin cá nhân trước khi chia sẻ. Quyền xem log không tự cho phép restart, xóa dữ liệu hay đổi cấu hình. Nếu không có quyền xem run/app, dừng thao tác đó và yêu cầu quyền đúng phạm vi.

| Triệu chứng | Đường kiểm tra |
| --- | --- |
| Không có service được chọn | Kiểm tra diff và [bộ chọn service](../.github/scripts/changed-services.sh); dùng manual deploy khi thực sự cần phát hành lại. |
| CI lỗi | Chạy kiểm tra do `Makefile` của service sở hữu; sửa lỗi trước khi deploy. |
| Thiếu secrets hoặc deploy bị từ chối | Kiểm tra environment, tên app và quyền App Token theo [_build-deploy.yml](../.github/workflows/_build-deploy.yml); không in giá trị secret. |
| CapRover không pull được image | Kiểm tra package tồn tại và quyền registry đọc đúng package. |
| Client 502 hoặc không gọi được API | Kiểm tra container port, runtime upstream nội bộ và log app; dùng [cấu hình client](client-workspace.md#development-and-deployment). |
| Chat không trả lời | Kiểm tra chat API và cấu hình provider riêng; deploy thành công không chứng minh tài khoản OpenAI có quyền dùng runtime. |

## Khôi phục

Đường khôi phục qua repository là PR revert vào đúng branch môi trường, chạy kiểm tra rồi để pipeline triển khai lại service bị ảnh hưởng. Chạy lại workflow trên cùng branch vẫn dùng revision được chọn; ô `services` không phải đầu vào cho commit SHA tùy ý. Không dựa vào moving tag để xác định chính xác bản cũ.

Nếu khôi phục image trực tiếp ngoài pipeline, trước tiên xác nhận image cũ còn tồn tại, đúng app/môi trường, và tương thích với dữ liệu hiện tại; người vận hành phải có quyền cho thao tác đó. Sau đó đối chiếu lại repository và app để tránh lần deploy tiếp theo đưa lỗi trở lại. Không xem image rollback là phương án hoàn tác migration hoặc dữ liệu.

## Kết nối từ sandbox OpenAI: thiết kế chưa provision

Mạng riêng `srv-captain--...` phục vụ app trong cluster; sandbox do OpenAI quản lý nằm ngoài mạng đó. Để runtime này gọi MCP của ShopOps, cần một ingress có thể truy cập từ bên ngoài, xác thực chặt và giới hạn đúng người dùng/shop/công cụ. Giữ tách quyền đọc dữ liệu và quyền ghi shop như [thiết kế runtime](system-architecture.md) yêu cầu.

Đây là yêu cầu kết nối của thiết kế, chưa phải endpoint đã cấu hình hay quyền đã cấp. Không public toàn bộ API nội bộ để giải quyết đường mạng; lựa chọn ingress, xác thực và provisioning cần được quyết định khi triển khai tích hợp đó.
