---
title: Bằng chứng Không tiết lộ (Zero-Knowledge Proofs)
description: Giải thích cơ chế Zero-Knowledge Proofs trong HieraChain, bao gồm ZKProver, ZKVerifier và các chế độ hoạt động.
icon: material/shield-key
---

# Bằng chứng Không tiết lộ (Zero-Knowledge Proofs)

HieraChain cung cấp interface proof ZK cho việc submit từ Sub-chain lên MainChain. Triển khai hiện tại hỗ trợ mock proof cho phát triển; proving và verification production chưa được triển khai.

### 1. Cơ chế Hoạt động của ZKProver & ZKVerifier

Hệ thống cung cấp hai module cốt lõi đảm nhiệm công việc này:

* **`ZKProver`** (Nằm tại Sub-chain - `hierachain/security/zk_prover.py`):
  
    * Đóng vai trò là bên chứng minh (Prover).
    * Đầu vào proof Sub-chain dùng Merkle root của event trong block trước và block mới nhất.
    * Triển khai mock hiện tại gắn các đầu vào này vào một hash. Nó không chứng minh chuyển trạng thái projection entity hoặc xác thực quy tắc nghiệp vụ.

* **`ZKVerifier`** (Nằm tại Main-chain - `hierachain/security/verify/zk_verifier.py`):
  
    * Đóng vai trò là bên xác minh (Verifier).
    * Với mock proof, `ZKVerifier` kiểm tra định dạng và commitment tới public inputs được cung cấp.
    * Proof bị từ chối sẽ chặn submission lên MainChain khi `HRC_ENABLE_ZK_PROOFS=true` và có cung cấp proof, hoặc khi `HRC_ZK_REQUIRED_MAINCHAIN=true`; mặc định cả hai thiết lập đều là `false`. Mock commitment có thể giả mạo và không cung cấp bảo đảm zero-knowledge production.

### 2. Các Chế độ Hoạt động (Modes)

Zero-Knowledge Proofs trong HieraChain hỗ trợ hai mode chạy tùy theo môi trường triển khai thực tế của Sub-chain (linh hoạt cấu hình qua biến môi trường `HRC_ZK_MODE`):

#### a. Mock Mode (Mặc định)

* Đây là chế độ phát triển (Dev) hoặc môi trường kiểm thử (Testing).
* Mock mode dùng định dạng `mock_zkp_v2\x00` với commitment SHA-256 tới public inputs; không chạy circuit SNARK.
* Hỗ trợ quá trình dev tích hợp Main/Sub mà không yêu cầu cấu hình tài nguyên phần cứng lớn.

#### b. Production Mode (unimplemented)

* Đây là interface dành cho production, hiện chưa được hỗ trợ.
* Đòi hỏi thư mục khóa chứng minh ở biến `HRC_ZK_PROVING_KEY` và khóa xác minh ở `HRC_ZK_VERIFICATION_KEY`.
* Các hook production nội bộ `_generate_production_proof()` và `_verify_production()` gây `NotImplementedError`. `ZKProver.generate_proof()` công khai bắt lỗi tạo proof và trả `ZKProofResult` không thành công; `generate_proof_bytes()` gây `ZKProvingError`, còn `ZKVerifier.verify()` bọc lỗi backend thành `ZKVerificationError`.

### 3. Public Inputs (Đầu vào Công khai)

Theo định nghĩa của `ZKPublicInputs`, các đối số đầu vào (được cả Prover và Verifier đồng bộ thống nhất) bao gồm:

* **`old_state_root` (str)**: Merkle root của event trong block ngay trước đó; đường submit dùng `genesis` khi không có block trước.
* **`new_state_root` (str)**: Merkle root của event trong block mới nhất, có fallback block hash hiện hành khi cần.
* **`block_index` (int)**: Số thứ tự block được gắn vào proof; tầng submission vẫn phải kiểm tra freshness và chống trùng.
* **`sub_chain_name` (str)**: ID hoặc tên định danh đầy đủ của Sub-chain đẩy Proof.

Các tham số này đều được serialize định dạng JSON bytes chuẩn hóa chặt chẽ (sử dụng `sort_keys=True`) trước khi đem đi hash sinh Proof.

`WorldState.get_state_root()` băm projection entity phục vụ truy vấn và là root chẩn đoán riêng. Đường proof liên cấp hiện tại không truyền root này. Các hook production chưa được triển khai; API công khai báo việc này qua kết quả và exception nêu trên. Việc làm rõ root không triển khai circuit ZK production.
