---
title: "Decentralized Zero-Knowledge Proofs"
description: "Phạm vi ZK hiện tại: fixture mock cho luồng proof và placeholder production chưa hỗ trợ."
icon: material/brain
---

# Decentralized Zero-Knowledge Proofs

HieraChain cung cấp interface prover và verifier cho luồng proof liên chuỗi. Chế độ đã triển khai là mock phát triển, dùng commitment SHA-256 của public inputs. Nó không chứng minh quy tắc nghiệp vụ, tính đúng đắn của bước chuyển trạng thái hay tính riêng tư zero-knowledge. Tạo và xác minh proof production chưa được triển khai.

## 1. ZK Prover

**File**: `hierachain/security/zk_prover.py`

* `ZKProver(mode="mock")` tạo fixture chứa hash của public inputs và phần đệm ngẫu nhiên. Bất kỳ ai có inputs đều có thể tạo commitment khớp.
* `ZKProver(mode="production").generate_proof(...)` trả `ZKProofResult(success=False, proof=b"", error=...)` vì backend production chưa triển khai.
* `generate_proof_bytes(...)` phát sinh `ZKProvingError` khi tạo thất bại. Nạp proving key hay cấu hình circuit path không triển khai backend.

## 2. ZK Verifier

**File**: `hierachain/security/verify/zk_verifier.py`

* Xác minh mock so sánh commitment với hash của public inputs. Hash khớp không tạo bằng chứng toán học về bước chuyển trạng thái hợp lệ.
* Với inputs hợp lệ, xác minh production phát sinh `ZKVerificationError` bọc lỗi backend chưa triển khai; inputs sai trả `False` trước bước gọi backend.
* Nạp verification key không làm cho xác minh production khả dụng.

## 3. Cấu hình và ranh giới runtime

`HRC_ENABLE_ZK_PROOFS` mặc định là `false`; `HRC_ZK_MODE` mặc định là `mock`. Bật xác minh không cài backend production. Chỉ dùng mock cho luồng proof phát triển và kiểm thử. Chỉ đặt `HRC_ZK_MODE=production` không tạo được triển khai ZK hoạt động.

Xác minh chữ ký block, Merkle root và điểm neo MainChain bền vững là các cơ chế toàn vẹn riêng đã triển khai. Không được mô tả chúng là zero-knowledge proof về tính đúng đắn nghiệp vụ. Ứng dụng cần xác thực ZK thật phải có backend tạo/xác minh và hợp đồng circuit được triển khai, kiểm chứng riêng.

## Liên quan

* [Kiến trúc phân cấp và phạm vi hỗ trợ tính năng](../modules/hierarchical.md)
* [Authorization & Access Control](./authorization-access-control.md)
