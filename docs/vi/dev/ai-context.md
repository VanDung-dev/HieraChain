---
title: "AI Context Definition - HieraChain"
description: "Chỉ dẫn cốt lõi (System Instructions) cho AI để ngăn chặn ảo giác và định hướng tư duy trong dự án HieraChain."
icon: material/robot
---

# AI Context Definition - HieraChain

!!! abstract "System Prompt for AI Assistants"
    File này chứa các chỉ dẫn cốt lõi (System Instructions) để ngăn chặn "ảo giác" (hallucination) của AI khi làm việc với HieraChain.

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

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**
    
    * HieraChain là hệ thống Enterprise Blockchain tập trung vào Data Audit, không phải Cryptocurrency.
    * File này đóng vai trò "System Prompt" mở rộng để định hướng tư duy cho AI.

    **DECISION**
    
    * Loại bỏ hoàn toàn các khái niệm Token, Gas, Mining để tránh rào cản pháp lý và nhận thức sai lệch trong môi trường doanh nghiệp.
    * Sử dụng thuật ngữ "Ordering" và "Validation" thay cho "Mining".

    **ASSUMPTION**
    
    * AI Model thường có thiên kiến (bias) gắn liền Blockchain với Crypto/Web3, do đó cần chỉ dẫn phủ định (Negative Constraints) rõ ràng.

    **INVARIANT**
    
    * **No Crypto Terms**: Mọi code hoặc tài liệu chứa từ khóa `coin`, `token`, `mining` đều bị coi là vi phạm (Invalid).
    * **Identity-First**: Mọi hành động đều gắn với định danh (MSP ID), không có ẩn danh.
    * **Transaction Scope**: Thuật ngữ `Transaction` chỉ được dùng với nghĩa **System/Database Transaction** (Technical Envelope), tuyệt đối không ám chỉ **Payment/Money Transfer**.
