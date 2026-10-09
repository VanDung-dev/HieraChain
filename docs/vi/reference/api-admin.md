---
title: API Admin
description: "Tài liệu REST API Admin của HieraChain: Quản trị hệ thống, xác thực node và kiểm tra trạng thái."
icon: material/numeric-3-circle
---

# API Admin

## Endpoint và quyền truy cập

Router được định nghĩa trong `hierachain/api/admin/endpoints.py`; các mô hình yêu cầu và phản hồi nằm trong `schemas.py`.

| Endpoint | Quyền truy cập và hành vi |
|:---------|:--------------------|
| `POST /api/admin/verify-identity` | Yêu cầu phạm vi `chains` khi bật xác thực bằng API key; ký thử thách có tiền tố phân biệt miền |
| `GET /api/admin/status` | Được miễn xác thực API key toàn cục; trả về trạng thái nút khi hierarchy manager khả dụng |
| `POST /api/admin/chains/{chain_name}/secure-events` | Yêu cầu phạm vi `chains` khi xác thực; kiểm tra chữ ký sự kiện trước khi gửi vào chuỗi |

Nếu triển khai cần hạn chế truy cập công khai vào trạng thái, hãy bảo vệ endpoint này tại reverse proxy. Route trạng thái không có dependency `require_chain_access`.

## Xác minh danh tính nút

`VerifyIdentityRequest` chứa chuỗi `challenge`. Handler ký các byte sau:

```python
payload = b"HRC_IDENTITY_CHALLENGE:" + challenge.encode("utf-8")
```

Handler không giải mã thử thách thành byte từ chuỗi thập lục phân. Phản hồi chứa `status`, `node_id`, `signature` và `challenge` ban đầu. Xác minh chữ ký trên cùng dữ liệu UTF-8 có tiền tố bằng khóa công khai đã được phê duyệt của nút. Nếu cần chống phát lại, client phải tạo thử thách mới và theo dõi việc sử dụng nó.

```bash
curl -X POST http://localhost:2661/api/admin/verify-identity \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{"challenge": "abcd1234"}'
```

Dependency nạp `LocalKeyProvider.from_file()` từ `HRC_VALIDATOR_IDENTITY`. Provider này đọc trường `private_key`. Trong khi đó, bộ nạp khóa ký khối yêu cầu đầy đủ các trường danh tính nút được mô tả tại [Sao lưu khóa](../workflows/key-backup.md). Nếu cả hai bộ nạp dùng chung một tệp, tệp phải đáp ứng cả hai định dạng và dùng cùng khóa ký. Tệp khóa bị thiếu hoặc không đọc được trả về HTTP 401; endpoint này không tạo khóa tạm thời.

## Trạng thái nút

```bash
curl -s http://localhost:2661/api/admin/status
```

`NodeStatusResponse` chứa `status`, `version`, `chains_active`, `license_active` và `uptime`. Phiên bản lấy từ `hierachain/config/version.py`; thời gian hoạt động được định dạng từ thời điểm khởi động manager. Hiện tại, `license_active` được gán cố định là `True`, không phải kết quả từ dịch vụ xác minh giấy phép.

## Gửi sự kiện có chữ ký

`SecureEventRequest` yêu cầu `entity_id`, `event_type`, `sender` và `signature`; `details` mặc định là đối tượng rỗng. `sender` và `signature` phải chứa dữ liệu thập lục phân với tiền tố `0x`. Các trường tùy chọn gồm `nonce`, `timestamp` và `chain_id`; trường không được định nghĩa sẽ bị từ chối. Details bị giới hạn ở 1 MiB JSON sau tuần tự hóa và độ sâu 10.

Handler từ chối `chain_id` khác với tên chuỗi trong đường dẫn, hoặc timestamp lệch quá 300 giây so với thời gian máy chủ. Nó gọi `SignatureVerifier.verify_event_signature()` trước `chain.add_event()`.

`SecureEventResponse` chứa `status`, `event_hash` và `timestamp` của máy chủ. Dù giá trị trạng thái là `committed`, handler gọi luồng tiếp nhận bất đồng bộ của Sub-Chain. `event_hash` là mã định danh lần gửi được trả về; cần đọc các khối đã hoàn tất để xác nhận đã ghi bền vững. Việc route chấp nhận chữ ký không khiến quá trình tạo khối trở thành đồng bộ.

## Mã trạng thái

| Mã | Ý nghĩa |
|:-----|:--------|
| 200 | Handler trả về thành công |
| 401 | Xác thực API key thất bại hoặc provider danh tính không nạp được khóa |
| 403 | Khóa đã xác thực thiếu phạm vi quyền yêu cầu |
| 404 | Chuỗi đích của sự kiện có chữ ký không tồn tại |
| 422 | Mô hình yêu cầu, tên chuỗi, khoảng thời gian hoặc chữ ký sự kiện không hợp lệ |
| 500 | Quá trình ký, tính trạng thái hoặc gửi sự kiện phát sinh lỗi nội bộ |

## Liên quan

* [Cấu hình](config.md)
* [Bảo mật](../modules/security.md)
* [Gửi sự kiện](../workflows/event-submission.md)
