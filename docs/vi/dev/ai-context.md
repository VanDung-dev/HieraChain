---
title: "AI Context Definition - HieraChain"
description: "Chỉ dẫn cốt lõi (System Instructions) cho AI để ngăn chặn ảo giác và định hướng tư duy trong dự án HieraChain."
icon: material/robot
---

# AI Context Definition - HieraChain

!!! abstract "System Prompt for AI Assistants"
    File này chứa các chỉ dẫn cốt lõi (System Instructions) bằng tiếng Việt để định hướng tư duy cho AI khi làm việc với HieraChain. Để xem hướng dẫn kỹ thuật chi tiết và đầy đủ nhất dành cho Coding Agents (English), vui lòng tham khảo **[AGENTS.md](../../../AGENTS.md)**.

## Bản chất dự án

**HieraChain LÀ:**

* Một Blockchain Ledger **Doanh nghiệp (Enterprise)**.
* Tập trung vào **Data Audit (Kiểm toán dữ liệu)**, Traceability (Truy xuất nguồn gốc) và Integrity (Toàn vẹn).
* Kiến trúc phân cấp (Main Chain - Sub Chain) để mở rộng (Scalability).
* Sử dụng **Apache Arrow** làm cấu trúc dữ liệu lõi.

**HieraChain KHÔNG PHẢI LÀ:**

* **KHÔNG** phải Tiền mã hóa (Cryptocurrency).
* **KHÔNG** có Token, Coin, Gas Fee, Mining, Wallet, Address (ví tiền).
* **KHÔNG** dùng để chuyển tiền (Payment).

## Quy tắc cấm kỵ

Khi phân tích mã nguồn hoặc viết tài liệu, AI **TUYỆT ĐỐI KHÔNG** được sử dụng hoặc suy diễn các khái niệm sau:

| Khái niệm cấm | Thay thế bằng | Lý do |
|---|---|---|
| Mining (Đào coin) | **Ordering / Validation** | HieraChain dùng Ordering Service và Node Validator được cấp quyền. |
| Gas Fee | **Resource Quota / Throughput** | Doanh nghiệp trả phí hạ tầng, không trả phí từng giao dịch. |
| Wallet / Address | **Identity (MSP ID) / Certificate** | Định danh dựa trên PKI/CA, không phải địa chỉ ví ẩn danh. |
| Token / Coin | **Asset / Record / State** | Dữ liệu là tài sản thông tin, không phải tiền tệ. |
| Smart Contract (ETH style) | **Domain Contract / Chaincode** | Logic nghiệp vụ (Python class), không phải máy ảo EVM. |

## Ngữ cảnh mã nguồn

Hệ thống có cơ chế **Hard Enforcement** (Cưỡng chế cứng) ngay trong code để chặn các thuật ngữ tiền ảo.

* **File**: `hierachain/core/utils.py`
* **Function**: `validate_no_cryptocurrency_terms`
* **Logic**: Nếu Event chứa từ khóa như `coin`, `token`, `wallet` -> Hệ thống sẽ từ chối xử lý (Raise Error).

```python
# Trích đoạn thực tế từ hierachain/core/utils.py
crypto_terms = [
    "mining", "coin", "token", "wallet", "address",
    "fee", "reward", "coinbase" 
    # Lưu ý: "transaction" có thể được dùng với nghĩa "Database Transaction", 
    # nhưng cần thận trọng ngữ cảnh.
]
```

## Định hướng tư duy

Khi người dùng hỏi về "Consensus" (Đồng thuận):

* **Đừng nghĩ đến**: Proof of Work (Bitcoin), Proof of Stake (Ethereum).
* **Hãy nghĩ đến**: Raft, Paxos, PBFT, Proof of Authority (PoA), Proof of Federation (PoF).

Khi người dùng hỏi về "Ledger" (Sổ cái):

* **Đừng nghĩ đến**: Số dư tài khoản (Account Balance).
* **Hãy nghĩ đến**: Nhật ký sự kiện (Event Log), Báo cáo kiểm toán (Audit Trail).
