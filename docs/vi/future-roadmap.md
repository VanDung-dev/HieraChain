---
title: "Future Roadmap"
description: "Định hướng công nghệ: Python Free-threading và Rust Core Acceleration."
icon: material/road-variant
---

# Lộ trình Tương lai: Hiệu năng & Đa luồng (Python vs Rust)

Tài liệu này đề cập đến các vấn đề hiệu năng hiện tại của Python và định hướng công nghệ của HieraChain trong tương lai.

## Vấn đề với Python "Thuần" (Pure Python)

HieraChain được thiết kế với kiến trúc hướng tới tương lai để tận dụng khả năng xử lý song song. Tuy nhiên, chúng ta đang đối mặt với thực tế:

* **Python GIL (Global Interpreter Lock)**: Các phiên bản Python hiện tại vẫn bị giới hạn bởi GIL, khiến việc tận dụng đa nhân CPU (Multi-core) chưa tối ưu cho các tác vụ CPU-bound như Blockchain Consensus.
* **Python 3.14+ (Free-threading)**: Mặc dù Python 3.13/3.14 đã bắt đầu hỗ trợ "no-GIL" (Free-threading), nhưng nó **chưa thực sự ổn định** để chạy Production cho các hệ thống tài chính/dữ liệu quan trọng.

=> **Hệ quả**: Nếu bạn chạy HieraChain ở chế độ "Thuần Python" (Pure Python), hiệu năng sẽ bị giới hạn đáng kể khi tải cao.

## Giải pháp Hiệu năng cao (Rust Acceleration)

Để giải quyết bài toán hiệu năng ngay lập tức mà không chờ Python hoàn thiện Free-threading, chúng tôi cung cấp các giải pháp thay thế dựa trên ngôn ngữ **Rust**:

### Tự tích hợp (Self-Managed)

Bạn có thể sử dụng thư viện Consensus viết bằng Rust:

* **Repository**: [https://github.com/VanDung-dev/HieraChain-Consensus](https://github.com/VanDung-dev/HieraChain-Consensus)
* **Mô tả**: Đây là thư viện Consensus hiệu năng cao, sử dụng PyO3 để giao tiếp với Python.
* **Lưu ý**: Bạn sẽ phải **TỰ CẤU HÌNH** (Manual Configuration) và sửa đổi code để kết hợp thư viện này vào HieraChain hiện tại.

### hrc-core (Enterprise / Lazy Mode)

* **hrc-core là gì?**: Đây là nhân (kernel) của HieraChain được viết **thuần bằng Rust** (Native Rust) nhưng vẫn giữ giao diện Python (Python Bindings) để dễ sử dụng. Nó mang lại hiệu năng tối đa của Rust với sự tiện lợi của Python.
* **Tình trạng**: Hiện tại `hrc-core` đang trong giai đoạn thử nghiệm và hoàn thiện.

---

*Tài liệu này nhằm định hướng cho các Developer muốn tối ưu hóa hiệu năng HieraChain vượt giới hạn của Python hiện tại.*

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Python GIL hiện tại giới hạn hiệu năng CPU-bound của HieraChain.
    * `hrc-core` là giải pháp thay thế viết bằng Rust.

    **DECISION**

    * Duy trì Python làm giao diện chính (Interface) vì tính dễ dùng.
    * Dịch chuyển các tác vụ nặng (Consensus, Crypto) xuống tầng Rust (Extension Module) theo lộ trình.

    **ASSUMPTION**

    * Python 3.14+ (Free-threading) có thể sẽ ổn định vào năm 2027-2028.
    * Cộng đồng doanh nghiệp ưu tiên hiệu năng/ổn định hơn là sự thuần khiết ngôn ngữ.

    **INVARIANT**

    * Mọi module Rust phải có Python binding (PyO3).
    * API Python không thay đổi (Backward Compatibility) khi chuyển đổi backend.
