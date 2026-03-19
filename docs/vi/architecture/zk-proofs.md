---
title: Bằng chứng Không tiết lộ (Zero-Knowledge Proofs)
description: Giải thích cơ chế Zero-Knowledge Proofs trong HieraChain, bao gồm ZKProver, ZKVerifier và các chế độ hoạt động.
icon: material/shield-key
---

# Bằng chứng Không tiết lộ (Zero-Knowledge Proofs)

HieraChain sử dụng **Zero-Knowledge Proofs (ZK)** để đảm bảo tính xác thực của các giao dịch trên hệ thống phân cấp mà không cần tiết lộ toàn bộ dữ liệu chi tiết của từng sự kiện (Event). Các Sub-chain sẽ tạo Proof chứng minh một quá trình chuyển đổi trạng thái là hợp lệ, và Main-chain sẽ tiến hành xác minh Proof đó.

### 1. Cơ chế Hoạt động của ZKProver & ZKVerifier

Hệ thống cung cấp hai module cốt lõi đảm nhiệm công việc này:

- **`ZKProver`** (Nằm tại Sub-chain - `hierachain/security/zk_prover.py`):
  - Đóng vai trò là bên chứng minh (Prover).
  - Khi một Sub-chain sinh ra một block mới, nó tạo ra một trạng thái mới (World State).
  - `ZKProver` sẽ sinh ra các đoạn mã Proof để chứng minh cho logic chuyển trạng thái từ `old_state_root` sang `new_state_root` trong `block_index` tương ứng vừa được kích hoạt.

- **`ZKVerifier`** (Nằm tại Main-chain - `hierachain/security/verify/zk_verifier.py`):
  - Đóng vai trò là bên xác minh (Verifier).
  - Khi nhận được tín hiệu Proof từ Sub-chain gửi lên Main-chain, `ZKVerifier` sẽ phân tích và xác minh tính hợp lệ của toán học cũng như tính toàn vẹn trạng thái.
  - Giải quyết triệt để nguy cơ **Fake Proofs** (Chứng cứ giả). Nếu Proof không vượt qua xác minh, giao dịch đính kèm trên Main-chain sẽ bị từ chối thẳng thừng.

### 2. Các Chế độ Hoạt động (Modes)

Zero-Knowledge Proofs trong HieraChain hỗ trợ hai mode chạy tùy theo môi trường triển khai thực tế của Sub-chain (linh hoạt cấu hình qua biến môi trường `ZK_MODE`):

#### a. Mock Mode (Mặc định)

- Đây là chế độ phát triển (Dev) hoặc môi trường kiểm thử (Testing).
- Mock Mode mô phỏng lại Groth16/Plonk ZK-SNARK bằng cách tạo ra một định dạng proof giả lập kích thước 2KB - 4KB với `mock_zkp_v2\x00`.
- Thay vì chạy circuit thuật toán, mock mode sử dụng tính toán hàm lượng băm nội suy (`hashlib.sha256`) đối với các tham số đầu vào (Public Inputs) và giả lập một độ trễ từ 100-500ms để đảm bảo giống với hệ thống proof thực.
- Hỗ trợ quá trình dev tích hợp Main/Sub mà không yêu cầu cấu hình tài nguyên phần cứng lớn.

#### b. Production Mode (ZoKrates)

- Đây là chế độ vận hành sản xuất thực tế trên môi trường Mainnet/Enterprise.
- Đòi hỏi thư mục khóa chứng minh ở biến `ZK_PROVING_KEY_PATH` và khóa xác minh ở `ZK_VERIFICATION_KEY_PATH`.
- Proof được sinh ra qua một External Service (như ZoKrates) chứa những phương trình tính toán hàm bậc cao SNARKs vô cùng an toàn và khó giả mạo.

### 3. Public Inputs (Đầu vào Công khai)

Theo định nghĩa của `ZKPublicInputs`, các đối số đầu vào (được cả Prover và Verifier đồng bộ thống nhất) bao gồm:

- **`old_state_root` (str)**: Merkle Root của World State ở block ngay trước đó. Phải là mã hash hợp lệ.
- **`new_state_root` (str)**: Merkle Root mới nhất sau khi các event được đưa vào block cập nhật hiện tại.
- **`block_index` (int)**: Số thứ tự block (cơ chế này giúp chặn hoàn toàn rủi ro Replay attacks).
- **`sub_chain_name` (str)**: ID hoặc tên định danh đầy đủ của Sub-chain đẩy Proof.

Các tham số này đều được serialize định dạng JSON bytes chuẩn hóa chặt chẽ (sử dụng `sort_keys=True`) trước khi đem đi hash sinh Proof.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Mã nguồn tài liệu tham chiếu: `hierachain/*` (Python >= 3.10 theo `pyproject.toml`).
    * Script CLI: `hrc` (định nghĩa tại `[project.scripts]` trong `pyproject.toml`).
    * API server: `hierachain/api/server.py` (có thể chạy bằng `python -m hierachain.api.server`).

    **DECISION**

    * Dùng Markdown, tách rõ các khối FACT / DECISION / ASSUMPTION / INVARIANT / EDGE CASES.
    * Tổ chức nội dung theo khung chuẩn thống nhất.

    **ASSUMPTION**

    * Người đọc đã cài Python 3.10+ và có quyền truy cập internet để cài dependencies.
    * Môi trường phát triển sử dụng `venv` hoặc công cụ tương đương.

    **INVARIANT**

    * FACT phải bám sát mã nguồn hiện tại (tên file, chữ ký API, đường dẫn).
    * Không pha trộn nội dung tiếp thị trong tài liệu kỹ thuật.

    **EDGE CASES**

    * Khác biệt shell giữa Windows (PowerShell) và Linux/macOS (bash) khi kích hoạt venv.
    * Mạng nội bộ hạn chế có thể ảnh hưởng quá trình cài gói.
