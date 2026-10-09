---
title: "Data Schema & Giao thức"
description: "Định nghĩa cấu trúc dữ liệu (Apache Arrow) và giao thức luồng dữ liệu trong HieraChain."
icon: material/file-tree
---

# Lược đồ dữ liệu và giao thức

HieraChain dùng JSON cho yêu cầu REST và bảng Apache Arrow để lưu sự kiện trong khối. Payload sự kiện nhị phân chuẩn hóa giữ nguyên kiểu dữ liệu của details; các cột metadata Arrow phục vụ lọc và lập chỉ mục. Xem [Mô hình dữ liệu](./data-models.md) để biết quy tắc tuần tự hóa và tính hash.

## Sự kiện

Arrow `EVENT_SCHEMA` được định nghĩa trong `hierachain/core/block.py`.

| Trường | Kiểu Arrow | Mô tả |
|:------|:-----------|:------------|
| `entity_id` | `string` | Mã định danh thực thể nghiệp vụ |
| `event` | `string` | Loại sự kiện nội bộ |
| `timestamp` | `float64` | Dấu thời gian Unix |
| `details` | `map<string, string>` | Biểu diễn giá trị details dưới dạng chuỗi cho metadata Arrow |
| `details_cid` | `string` | Tham chiếu IPFS ngoài chuỗi, tùy chọn |
| `details_nonce` | `string` | Nonce AES-GCM công khai cho đối tượng ngoài chuỗi đã mã hóa |
| `data` | `binary` | Payload JSON chuẩn hóa của sự kiện giữ trường JSON và kiểu dữ liệu của details; bỏ trường byte cấp cao nhất |

`details_nonce` không phải khóa giải mã. Để truy xuất dữ liệu IPFS đã mã hóa, còn cần khóa mã hóa ổn định và metadata đã dùng làm AAD, nếu có. Xem [Lưu trữ IPFS](../workflows/ipfs-storage.md).

### Dữ liệu đầu vào REST

`EventRequest` trong `hierachain/api/ledger/schemas.py` yêu cầu `entity_id` và `event_type`. Trường tùy chọn gồm `details`, `details_cid`, `details_nonce`, `details_metadata`, `sender` và `signature`. Schema không có trường `timestamp`. Ledger API ánh xạ `event_type` sang trường nội bộ `event` và gán thời gian hiện tại của server.

Lược đồ Arrow bảy cột không có cột riêng cho `signature`, `zk_proof` hay `zk_public_inputs`. Trường JSON bổ sung vẫn có thể được lưu trong byte chuẩn hóa của sự kiện; riêng việc có trường đó không chứng minh rằng dữ liệu đã được xác minh mật mã.

HTTP SDK gửi dữ liệu sự kiện của bên gọi đến Ledger API dưới dạng JSON. SDK không bọc dữ liệu trong một đối tượng có chữ ký riêng hay tạo bằng chứng ZK. Việc gửi bằng chứng MainChain và ký header khối có quy tắc xác thực riêng.

## Khối

`Block.events` là một `pyarrow.Table`. Khi tuần tự hóa khối, các trường header sau được đưa vào:

| Trường | Ý nghĩa |
|:------|:--------|
| `index` | Vị trí khối trong chuỗi |
| `timestamp` | Thời điểm tạo khối |
| `previous_hash` | Hash của khối trước |
| `nonce` | Trường header được đưa vào tuần tự hóa và tính hash; PoA/PoF không dùng trường này cho đồng thuận dựa trên công việc tính toán |
| `merkle_root` | Gốc được tính từ các sự kiện của khối |
| `hash` | Hash đã tính của khối |
| `creator_id` | Danh tính nút ký khối |
| `signature` | Chữ ký Ed25519 của header khối chuẩn hóa |

Các trường header không phải một lược đồ sự kiện Arrow bổ sung. Bộ xác minh dùng bảng ánh xạ bên tạo khối sang khóa công khai đã được người vận hành phê duyệt để kiểm tra chữ ký.

## Tiếp nhận và ghi khối

1. Ledger API xác thực JSON đầu vào và gọi `SubChain.add_event()`.
2. Dịch vụ ordering ghi nhật ký và xếp hàng sự kiện. ID sự kiện được trả về xác nhận đã tiếp nhận; việc ghi khối diễn ra bất đồng bộ sau đó.
3. Bộ xử lý nền chứng nhận và gom sự kiện thành lô. Block manager gán chỉ số và liên kết khối, chạy bước hoàn tất đồng thuận, ký header và lưu khối bền vững trước khi xếp hàng cho consumer của Sub-Chain.
4. Consumer xác thực và áp dụng nguyên trạng khối đã lưu, cập nhật WorldState và kiểm tra đã đến lúc gửi bằng chứng hay chưa.

Xem [Gửi sự kiện](../workflows/event-submission.md) để biết cách xử lý lỗi. BFT là triển khai thư viện riêng; runtime MainChain/SubChain chọn PoA hoặc PoF.

## Tuần tự hóa và truyền tải

REST dùng JSON. Bảng sự kiện nội bộ và nhật ký sự kiện dùng biểu diễn Arrow với byte sự kiện chuẩn hóa để kiểm tra tính toàn vẹn. Mã truyền thông mạng nằm trong `hierachain/network/`; gói không cung cấp truyền tải Protobuf/gRPC. Không nên suy ra giao thức truyền tải từ định dạng bảng sự kiện.
