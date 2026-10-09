---
title: "Câu hỏi thường gặp"
description: "FAQ về cài đặt, cấu hình, API, bảo mật, hiệu năng và lưu trữ cho HieraChain."
icon: material/frequently-asked-questions
---

# Câu hỏi thường gặp

## Khởi động node thế nào?

Cấp identity, bản đồ trusted key và database theo [Bắt đầu nhanh](../getting-started/quickstart.md), rồi chạy `python -m hierachain` hoặc `hrc node start`. Port API mặc định là 2661. `/api/ledger/health` kiểm tra liveness; `/api/ledger/ready` kiểm tra phục hồi hierarchy.

## Bật xác thực thế nào?

Đặt `HRC_AUTH_ENABLED=true` trước khi khởi động và dùng `X-API-Key` (hoặc `HRC_API_KEY_NAME`). Production yêu cầu `HRC_API_KEYS_FILE` đọc được, không rỗng, có key đã cấp, user ID và quyền. Xem [Cấu hình](../reference/config.md).

## Có event ID nghĩa là block đã commit chưa?

Chưa. Sub-Chain ghi journal và đưa event vào queue khi nhận. Đọc block/event đã finalize trước khi dựa vào commit. Gửi proof lên MainChain thành công xác nhận lưu và đọc lại proof có chữ ký bền vững.

## MainChain và Sub-Chain là gì?

Sub-Chain lưu event nghiệp vụ. MainChain neo proof block của chúng. Root proof là Merkle root event trong block; `WorldState.get_state_root()` là root projection chẩn đoán riêng.

## Event dùng định dạng nào?

Request REST/SDK dùng `entity_id`, `event_type` và object JSON `details`. Event nội bộ dùng `event`. API cấp timestamp. Arrow biểu diễn cột detail bằng chuỗi, còn byte event canonical giữ payload phục vụ phục hồi.

## Dùng Redis làm backend ledger được không?

Storage hierarchy bền vững cần SQLite hoặc PostgreSQL. Redis có adapter phụ trợ, auth state và rate limit; startup hierarchy từ chối Redis làm storage block có chữ ký. Memory chỉ tồn tại trong process.

## ZK, contract, private data và ERP đã sẵn sàng production chưa?

Tạo/xác minh ZK production, thực thi contract và ghi private data chưa triển khai. Thực thi contract/ghi private data trả HTTP 501. Connector ERP vendor có sẵn chỉ mô phỏng; ứng dụng phải cung cấp adapter thật.

## Điều tra latency hoặc lỗi 503 thế nào?

Kiểm tra rate/payload limit API, Redis, giới hạn event pool/RAM ordering và log storage. PoA mặc định không thêm giãn cách, nhưng batching và I/O bền vững vẫn mất thời gian. Xem [Hiệu năng](../guides/performance.md).

## Kiểm thử và phát hành thế nào?

Chạy từng file test với storage biệt lập; xem [Kiểm thử](../dev/testing.md). Version package lấy từ `hierachain/config/version.py`; xem [Quy trình phát hành](../dev/release-process.md).
