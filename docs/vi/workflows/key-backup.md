---
title: "Sao lưu và khôi phục khóa"
description: "Các luồng sao lưu và khôi phục khóa hiện có trong HieraChain: khóa Ed25519 tạo bằng CLI và FileVaultProvider."
icon: material/key
---

# Sao lưu và khôi phục khóa

## Sao lưu danh tính nút

Việc ký khối yêu cầu danh tính nút cố định và bảng khóa khối tin cậy được người vận hành phê duyệt. `HRC_VALIDATOR_IDENTITY` trỏ đến JSON danh tính; `HRC_BLOCK_TRUSTED_KEYS_FILE` trỏ đến bảng khóa công khai tin cậy. Làm theo [Khởi động nhanh](../getting-started/quickstart.md) để chuẩn bị cả hai tệp.

Danh tính chứa `node_id`, `msp_id`, `signing_key`, `signing_public_key`, `transport_secret_key` và `transport_public_key`. Dùng công cụ bên ngoài để sao lưu đầy đủ danh tính và bảng khóa tin cậy với quyền truy cập hạn chế. Khôi phục chúng về đường dẫn đã cấu hình trước khi khởi chạy nút. Khóa ký riêng/công khai phải khớp nhau, và bảng tin cậy phải chứa khóa ký công khai đã được phê duyệt của nút đó.

Tạo khóa mới sẽ thay đổi khóa có thẩm quyền ký của danh tính. Cập nhật bảng tin cậy của mọi bộ xác minh bị ảnh hưởng qua quy trình cấp phát của hệ thống triển khai; chỉ sao chép khóa riêng mới không cấp quyền sử dụng khóa đó.

## Tệp cặp khóa CLI

`hierachain/cli/key.py` cung cấp các lệnh sau qua `hrc`:

```bash
hrc key generate --output validator_key.json
hrc key show --input validator_key.json
hrc key verify --input validator_key.json
```

JSON đầu ra mặc định chứa `private_key` và `public_key` dưới dạng chuỗi thập lục phân. Tệp được tạo với quyền `0600` trên hệ thống POSIX, và lệnh tạo khóa từ chối ghi đè tệp đã tồn tại. `show` che khóa riêng; `verify` kiểm tra khóa công khai có khớp với khóa riêng hay không.

Tệp hai trường này được `LocalKeyProvider.from_file()` chấp nhận. Nó không phải danh tính nút đầy đủ và không thể dùng trực tiếp làm `HRC_VALIDATOR_IDENTITY`. `python -m hierachain` khởi chạy API server; dùng `hrc` cho các lệnh khóa.

Sao lưu và khôi phục tệp khóa CLI là thao tác thủ công. Sau khi khôi phục tệp, chạy `hrc key verify --input validator_key.json`. CLI không cung cấp mã hóa, luân chuyển khóa tự động hay phân phối bản sao lưu.

## Kho khóa mã hóa cho phát triển và kiểm thử

`FileVaultProvider` trong `hierachain/security/key_provider.py` lưu cặp khóa trong kho được bảo vệ bằng mật khẩu. Nó dẫn xuất khóa Fernet bằng `PBKDF2HMAC(SHA256, 310_000 iterations)`; Fernet dùng AES-128-CBC và HMAC. Cấp mật khẩu cho hàm khởi tạo provider và giữ bản sao có thể khôi phục trong hệ thống quản lý bí mật của ứng dụng.

Provider này dùng mã hóa dẫn xuất từ mật khẩu cho tệp vault cục bộ. Phát triển và kiểm thử là phạm vi sử dụng được tài liệu nguồn nêu, nhưng mã không có điều kiện môi trường để chặn sử dụng trong production; mức độ phù hợp phụ thuộc vào biện pháp kiểm soát và yêu cầu của hệ thống triển khai. Tích hợp HSM hoặc KMS trong production cần `KeyProvider` riêng của ứng dụng. Kho khóa là một key provider, không thay thế JSON danh tính nút đầy đủ.

`HRC_VAULT_TOKEN` và `HRC_VAULT_PATH` cấu hình backend Vault riêng của `SecretManager`. Chúng không cung cấp mật khẩu cho `FileVaultProvider`. Việc cấp chứng chỉ MSP và thay đổi đồng thuận không kích hoạt sao lưu tự động.

## Liên quan

- [Danh tính MSP](./msp-identity.md): vòng đời chứng chỉ nội bộ
- [Mã hóa và khóa](../security/encryption-keys.md): provider và phạm vi sử dụng khóa
