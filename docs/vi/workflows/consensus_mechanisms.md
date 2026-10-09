---
title: "Cơ chế đồng thuận"
description: "So sánh và đặc tả kỹ thuật của các cơ chế đồng thuận PoA, PoF và BFT trong HieraChain."
icon: material/sync
---

# Cơ chế đồng thuận

## Lựa chọn runtime

MainChain chọn `HRC_MAINCHAIN_CONSENSUS`, fallback về `HRC_CONSENSUS_TYPE`; mặc định là `proof_of_authority`. Sub-Chain mặc định PoA và nhận `config` Python với `consensus_type="proof_of_federation"`. BFT là triển khai riêng trong `hierachain/consensus/bft/`; đặt `BFT_ENABLED` không nối BFT vào các đường chain này. Dùng selector PoA/PoF được tài liệu hóa; giá trị khác không phải công tắc kích hoạt BFT.

## So sánh triển khai

| Thuộc tính | PoA | PoF | Thành phần BFT |
|------------|-----|-----|----------------|
| Runtime hierarchy | Mặc định MainChain/Sub-Chain | Chọn federation rõ ràng | Cần tích hợp riêng |
| Signer finalization | Authority đã đăng ký | Validator đã đăng ký; validation buộc đúng leader nếu bật rotation | Giao thức bỏ phiếu PBFT |
| Interval mặc định | 0.0 giây | 5.0 giây | Cấu hình timeout giao thức |
| Kiểm tra giãn cách timestamp | Ít nhất nửa interval dương | Ít nhất 80% interval (mặc định 4 giây) | Giao thức riêng |
| Thành viên | Ít nhất một authority | `min_validators=3` để tạo block | `n >= 3f + 1` |
| ZK | Xác minh tùy chọn dùng chung | Xác minh tùy chọn dùng chung | Cờ môi trường dùng chung; xem giới hạn đầu vào BFT |

## Ordering và độ bền dữ liệu

`SubChain.add_event()` ghi journal và đưa event vào hàng đợi. Ordering gom event, finalize đồng thuận, ký header và lưu block trước khi đưa vào commit queue. Consumer Sub-Chain xác minh và áp dụng block đã commit mà không ghi lại. Xác nhận gửi event xảy ra trước finality. Ordering Sub-Chain mặc định dùng 50 event và batch timeout 1 giây; thời gian chờ này độc lập với giãn cách block PoA.

## Giới hạn PoF

`get_current_leader(index)` dùng danh sách validator đã sắp xếp và `index % count`. `validate_block()` kiểm tra cấu trúc, giãn cách timestamp, identity leader, chữ ký leader trên payload dựng lại trước finalization, và bước ZK tùy chọn dùng chung. Dù tên là `_verify_block_quorum()`, hàm này kiểm tra một chữ ký leader. `verify_quorum_signatures()` kiểm tra riêng chữ ký của các validator khác nhau với ngưỡng mặc định `floor(2n/3)+1`; đường finalize/validate block thông thường không thu thập hoặc bắt buộc quorum đó. Class này chưa triển khai failover leader tự động.

Đăng ký public key thật của validator. Nếu bỏ `public_key` khi gọi `add_validator()`, class tạo khóa không thuộc validator từ xa; không dùng cách này để cấp cấu hình mạng.

## Giới hạn ZK

`HRC_ENABLE_ZK_PROOFS=false` tắt kiểm tra ZK dùng chung. Nếu bật, xử lý proof thiếu còn phụ thuộc `HRC_ZK_REQUIRED_MAINCHAIN`. PoF không bắt buộc ZK riêng theo mặc định. Mock proof là fixture phát triển có thể tự tạo; tạo/xác minh `production` chưa triển khai. Block có chữ ký và Merkle anchor vẫn là các cơ chế toàn vẹn riêng.

## Cấu hình

```dotenv
HRC_MAINCHAIN_CONSENSUS=proof_of_authority
HRC_BLOCK_INTERVAL=0.0
HRC_ENABLE_ZK_PROOFS=false
HRC_ZK_REQUIRED_MAINCHAIN=false
```

`block_interval` của PoF là cấu hình đồng thuận riêng; `HRC_BLOCK_INTERVAL` điều khiển PoA. Hàm khởi tạo chuỗi hiện không áp dụng `CONSENSUS_FEDERATION_CONFIG`. BFT dùng cờ ZK chung, nhưng helper và lớp bọc request đặt operation ở các vị trí khác nhau; xem [BFT](../consensus/bft_consensus.md) trước khi dựa vào kiểm tra đó.

## Liên quan

* [PoA](../consensus/poa.md) · [PoF](../consensus/pof.md)
* [Luồng BFT](bft-consensus.md)
* [Gửi event](event-submission.md) · [Neo proof](proof-anchoring.md)
