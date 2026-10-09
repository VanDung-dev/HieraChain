---
title: "Bắt đầu nhanh"
description: "Thiết lập nhanh môi trường và chạy thử HieraChain trong vài phút."
icon: material/lightning-bolt
---

# Bắt đầu nhanh

Ví dụ này dùng ledger SQLite mới và một signer PoA. Chạy trong thư mục làm việc trống sau khi cài package. Không dùng lại thư mục đã có ledger hoặc identity.

## Cài đặt

Từ bản checkout mã nguồn:

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
uv sync --frozen --extra dev
source .venv/bin/activate
```

`uv sync` cài dependency cơ bản; `--extra dev` bổ sung công cụ phát triển. Trên Windows, kích hoạt bằng `.venv\Scripts\Activate.ps1`.

## Tạo identity ký cục bộ

Chạy đoạn Python sau một lần trong thư mục làm việc mới. Nó tạo identity đúng schema `NodeIdentity` và bản đồ public key tin cậy tương ứng. File đã tồn tại sẽ bị từ chối. Không đưa identity chứa private key vào Git.

```python
import json
import os
from pathlib import Path

import zmq
from hierachain.security.security_utils import KeyPair

signing = KeyPair.generate()
transport_public, transport_secret = zmq.curve_keypair()
identity = {
    "node_id": "local-node",
    "msp_id": "LocalMSP",
    "signing_key": signing.private_key,
    "signing_public_key": signing.public_key,
    "transport_public_key": transport_public.decode(),
    "transport_secret_key": transport_secret.decode(),
}
for filename, data in (
    ("identity.json", identity),
    ("trusted_block_keys.json", {"local-node": signing.public_key}),
):
    fd = os.open(Path(filename), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output)
```

Đặt các biến sau trong cùng terminal **trước khi import HieraChain**. Ví dụ shell POSIX này tắt dotenv, P2P và xác thực API chỉ cho demo cục bộ biệt lập:

```bash
export HRC_ENV=dev
export HRC_ENV_FILE=/dev/null
export HRC_STORAGE_BACKEND=sqlite
export DATABASE_URL=sqlite:///local-ledger.db
export HRC_VALIDATOR_IDENTITY="$PWD/identity.json"
export HRC_BLOCK_TRUSTED_KEYS_FILE="$PWD/trusted_block_keys.json"
export HRC_NODE_ID=local-node
export HRC_P2P_ENABLED=false
export HRC_AUTH_ENABLED=false
export HRC_ENABLE_ZK_PROOFS=false
export HRC_MAINCHAIN_CONSENSUS=proof_of_authority
export HRC_BLOCK_INTERVAL=0
```

SQLite lưu block trong `local-ledger.db`; journal ordering nằm ở `data/<chain-name>` tính từ thư mục làm việc. Giữ cả hai để phục hồi. Production cần cấp identity và API key riêng; xem [Cấu hình](../reference/config.md) và [Triển khai an toàn](../how-to/secure-deployment.md).

## Ghi event và neo proof

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
try:
    assert manager.create_sub_chain("supply_chain", "supply_chain")
    chain = manager.get_sub_chain("supply_chain")
    assert chain.register_entity("PROD-001", {"product": "sample"})
    assert manager.start_operation(
        "supply_chain", "PROD-001", "production_start", {"quantity": 100}
    )
    chain.flush_pending_and_finalize(timeout=10.0)
    assert any(
        event["event"] == "operation_start"
        for event in chain.get_events_by_entity("PROD-001")
    )
    assert manager.submit_proof_to_main_chain("supply_chain")
finally:
    manager.close()
```

`start_operation()` xác nhận gửi vào ordering. `flush_pending_and_finalize()` xử lý công việc đang chờ; truy vấn entity kiểm tra event nghiệp vụ đã vào block hoàn tất. Gửi proof phải thành công sau khi MainChain lưu bền vững và đọc lại. `close()` đóng orderer và storage do manager sở hữu. Dùng tên chain khác khi mở rộng ledger có sẵn.

PoA mặc định không thêm thời gian giãn cách block (`HRC_BLOCK_INTERVAL=0`). Ordering của Sub-Chain vẫn gom tối đa 50 event hoặc chờ tối đa 1 giây theo mặc định. PoF giữ cấu hình interval riêng là 5 giây.

## Khởi động API

Với cùng identity và database đã cấu hình, chạy:

```bash
python -m hierachain
```

Lệnh CLI tương đương là `hrc node start`. Mở `http://localhost:2661/docs`. `/api/ledger/health` kiểm tra liveness; `/api/ledger/ready` khởi tạo/kiểm tra phục hồi hierarchy. Việc nhận event là bất đồng bộ; đọc block hoàn tất trước khi dựa vào proof anchor.

## Bước tiếp theo

* [Kiến trúc](../architecture/overview.md)
* [API Ledger](../reference/api-ledger.md)
* [Phạm vi tính năng](../modules/hierarchical.md)
