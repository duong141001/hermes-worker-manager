# Hướng dẫn cài Hermes Worker Manager

Tài liệu này cài đủ bốn thành phần:

```text
Agent router:        smit-worker-router
Opaque handoff:      smit-opaque-handoff
Sanitization guard:  smit-sanitization-guard
Desktop UI:          smit-worker-router/plugin.js
```

## Điều kiện

- Hermes Agent/Desktop bản mới có lệnh `hermes plugins` và Desktop Plugin SDK.
- Đã cấu hình ít nhất một provider trong Hermes.
- Có Git.
- Chỉ cần Python/Node nếu muốn chạy tests.

## Cài tự động trên Windows

Mở PowerShell:

```powershell
git clone https://github.com/duong141001/hermes-worker-manager.git
cd hermes-worker-manager
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Nếu Sếp dùng `HERMES_HOME` riêng:

```powershell
$env:HERMES_HOME = 'D:\duong-dan\hermes'
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

## Cài tự động trên Linux/macOS/WSL

```bash
git clone https://github.com/duong141001/hermes-worker-manager.git
cd hermes-worker-manager
HERMES_HOME="$HOME/.hermes" bash scripts/install.sh
```

Installer sẽ:

1. Kiểm tra cấu trúc source.
2. Backup plugin cũ vào `$HERMES_HOME/backups/hermes-worker-manager-<timestamp>/`.
3. Copy đúng các file production, không copy test/cache.
4. Enable ba agent plugin với `--no-allow-tool-override`.
5. Không sửa provider, model, API key, endpoint hay credential.
6. Không tự tắt phiên Hermes đang chạy.

## Khởi động lại

Sau khi cài:

```bash
hermes gateway restart
```

Khởi động lại Hermes Desktop. Nếu Desktop đang mở, có thể dùng Command Palette → **Reload desktop plugins**. Desktop cũng tự theo dõi thư mục plugin và thường hot-reload trong vài giây.

## Cài thủ công

Agent plugins có thể cài trực tiếp từ subdirectory GitHub:

```bash
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-worker-router --enable
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-opaque-handoff --enable
hermes plugins install duong141001/hermes-worker-manager/plugins/smit-sanitization-guard --enable
```

Desktop plugin phải copy riêng:

```text
Nguồn:
  desktop-plugins/smit-worker-router/plugin.js

Đích:
  $HERMES_HOME/desktop-plugins/smit-worker-router/plugin.js
```

## Cấu hình lần đầu

1. Mở pane **Worker Manager**.
2. Chọn Provider đã đăng nhập trong Hermes.
3. Bấm ô model gọn để mở model catalog native của Hermes.
4. Chọn model và Reasoning/Fast phù hợp.
5. Chọn Handoff nếu provider thường; external-sanitized sẽ bị khóa On.
6. Bấm **Test selected worker profile**.
7. Mở pane riêng **Worker Monitor** để xem worker đang chạy, token, API calls và history.

## Profile động

Router luôn dispatch qua profile:

```text
smit-router-selected
```

Worker Manager chỉ cập nhật các field route hữu hạn như provider/model/reasoning/Fast. Nó không chủ động xóa các field bảo mật như:

```text
workdir
source_allowlist
docker_sandbox
allowed_toolsets
role
container/security/resource settings
```

Nếu chưa có profile, chọn provider/model trong UI để Hermes tạo phần route tối thiểu. Docker sandbox không được bật ngầm cho người dùng public; hãy cấu hình theo môi trường của Sếp.

## Kiểm tra cài đặt

```bash
hermes plugins list
```

Phải thấy:

```text
smit-worker-router
smit-opaque-handoff
smit-sanitization-guard
```

Trong Desktop phải có hai pane:

```text
Worker Manager
Worker Monitor
```

## Gỡ cài đặt

```bash
hermes plugins remove smit-worker-router
hermes plugins remove smit-opaque-handoff
hermes plugins remove smit-sanitization-guard
```

Xóa Desktop plugin:

```text
$HERMES_HOME/desktop-plugins/smit-worker-router/
```

Sau đó restart gateway/Desktop.

## Lưu ý bảo mật

- Không đưa `config.yaml`, `.env`, API key, token, endpoint riêng, log, transcript hoặc history lên Git.
- Opaque handoff chỉ làm mờ ngữ nghĩa; không phải mã hóa.
- Provider external vẫn có thể đọc payload được gửi tới họ.
- Chỉ dùng context public hoặc đã sanitize/de-identify.
