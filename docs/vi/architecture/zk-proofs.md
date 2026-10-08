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
    * Proof bị từ chối sẽ chặn submission tương ứng lên MainChain. Mock commitment có thể giả mạo và không cung cấp bảo đảm zero-knowledge production.

### 2. Các Chế độ Hoạt động (Modes)

Zero-Knowledge Proofs trong HieraChain hỗ trợ hai mode chạy tùy theo môi trường triển khai thực tế của Sub-chain (linh hoạt cấu hình qua biến môi trường `ZK_MODE`):

#### a. Mock Mode (Mặc định)

* Đây là chế độ phát triển (Dev) hoặc môi trường kiểm thử (Testing).
* Mock mode dùng định dạng `mock_zkp_v2\x00` với commitment SHA-256 tới public inputs; không chạy circuit SNARK.
* Thay vì chạy circuit thuật toán, mock mode sử dụng tính toán hàm lượng băm nội suy (`hashlib.sha256`) đối với các tham số đầu vào (Public Inputs) và giả lập một độ trễ từ 100-500ms để đảm bảo giống với hệ thống proof thực.
* Hỗ trợ quá trình dev tích hợp Main/Sub mà không yêu cầu cấu hình tài nguyên phần cứng lớn.

#### b. Production Mode (ZoKrates)

* Đây là interface dành cho production, hiện chưa được hỗ trợ.
* Đòi hỏi thư mục khóa chứng minh ở biến `ZK_PROVING_KEY_PATH` và khóa xác minh ở `ZK_VERIFICATION_KEY_PATH`.
* Các method production hiện gây `NotImplementedError`; cấu hình đường dẫn khóa không kích hoạt proving service bên ngoài.

### 3. Public Inputs (Đầu vào Công khai)

Theo định nghĩa của `ZKPublicInputs`, các đối số đầu vào (được cả Prover và Verifier đồng bộ thống nhất) bao gồm:

* **`old_state_root` (str)**: Merkle root của event trong block ngay trước đó; đường submit dùng `genesis` khi không có block trước.
* **`new_state_root` (str)**: Merkle root của event trong block mới nhất, có fallback block hash hiện hành khi cần.
* **`block_index` (int)**: Số thứ tự block được gắn vào proof; tầng submission vẫn phải kiểm tra freshness và chống trùng.
* **`sub_chain_name` (str)**: ID hoặc tên định danh đầy đủ của Sub-chain đẩy Proof.

Các tham số này đều được serialize định dạng JSON bytes chuẩn hóa chặt chẽ (sử dụng `sort_keys=True`) trước khi đem đi hash sinh Proof.

`WorldState.get_state_root()` băm projection entity phục vụ truy vấn và là root chẩn đoán riêng. Đường proof liên cấp hiện tại không truyền root này. Proving và verification production hiện gây `NotImplementedError`; việc làm rõ root không triển khai circuit ZK production.
