---
title: "CLI module"
description: "Công cụ dòng lệnh hrc và các nhóm lệnh: chain, node, event, store, verify — bám sát hierachain/cli/*."
icon: material/console
---

# CLI Module

## Mục đích

Cung cấp công cụ dòng lệnh thống nhất (`hrc`) để thao tác nhanh với HieraChain trong môi trường dev/ops/script.

## Kiến trúc & khái niệm

* Entry point: `pyproject.toml` → `[project.scripts] hrc = hierachain.cli.__init__:hrc`
* Nhóm lệnh chính: `hierachain/cli/{chain.py, node.py, event.py, store.py, verify.py}`
* Cấu hình CLI: `settings.CLI_CONFIG_FILE` (mặc định `chains.json`), `settings.CLI_LOG_LEVEL`

## Sử dụng cơ bản

```bash
hrc --help
```

Ví dụ (mang tính minh họa):

```bash
# Tạo Sub-Chain nhanh (tùy command hỗ trợ)
hrc chain create supply_chain --type generic

# Ghi sự kiện
hrc event add supply_chain --entity PROD-001 --type production_complete --details quantity=100

# Gửi proof lên Main Chain
hrc chain submit-proof supply_chain

# Truy vết thực thể
hrc event trace PROD-001 --chain supply_chain

# Kiểm tra chữ ký khối/sự kiện
hrc verify signature --file block.json --pubkey <hex>
```

## Cấu hình

* File cấu hình CLI: `chains.json` (mặc định theo `settings.CLI_CONFIG_FILE`).
* Mức log: `settings.CLI_LOG_LEVEL` (ví dụ `INFO`).

## Tính năng & hạn chế

* Tính năng: thao tác nhanh; dễ script hóa; phù hợp CI/CD.
* Hạn chế: phụ thuộc chức năng CLI đã được triển khai trong các module `cli/*`.

## Bảo mật & quyền truy cập

* Không in ra secret/API key trên console; sử dụng biến môi trường/secret manager khi cần.

## Xử lý lỗi & khắc phục

* Lệnh phải trả mã lỗi rõ ràng (exit code ≠ 0) khi thất bại; ghi log tối thiểu.

## Hiệu năng

* Các thao tác CLI thường là lệnh ngắn; tránh vòng lặp nặng trên máy User.

## Liên quan

* API v1 (thay thế/cổ điển qua HTTP): [API v1](../reference/api-v1.md)
* Config: [Config (Module)](config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Entry point CLI `hrc` được đăng ký trong `pyproject.toml` trỏ tới `hierachain.cli.__init__:hrc`.
    * Nhóm lệnh CLI được bố trí trong `hierachain/cli/*`.

    **DECISION**

    * Duy trì CLI như công cụ automation/dev tiện dụng song song với API HTTP.

    **ASSUMPTION**

    * User có quyền shell và đã kích hoạt môi trường Python phù hợp.

    **INVARIANT**

    * CLI không làm lộ thông tin nhạy cảm ra stdout/stderr.

    **EDGE CASES**

    * Thiếu quyền ghi đọc file cấu hình → báo lỗi và hướng dẫn khắc phục.
    * Endpoint API không reachable (khi CLI phụ thuộc API) → hiển thị gợi ý kiểm tra cổng/tường lửa.
