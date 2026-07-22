---
title: "Thêm API Ledger Endpoint"
description: "Các bước để thêm một endpoint mới vào API Ledger, kết nối schema/handler và kiểm thử nhanh với curl."
icon: material/plus-network
---

# Thêm API Ledger Endpoint

## Mục tiêu

Hướng dẫn từng bước để thêm một endpoint mới vào FastAPI router (Ledger) của HieraChain, bao gồm định nghĩa Pydantic schema, viết handler, cập nhật router và kiểm thử nhanh bằng `curl`.

## Bước 1: Chuẩn bị Schema (tùy chọn)

* Mở `hierachain/api/ledger/schemas.py`.
* Thêm một lớp Pydantic nếu endpoint cần payload mới, ví dụ:

```python
class PingRequest(BaseModel):
  message: str

class PingResponse(BaseModel):
  ok: bool
  echo: str
```

## Bước 2: Thêm Handler trong Router

* Mở `hierachain/api/ledger/router.py`.
* Import schema (nếu có) và thêm route vào `APIRouter(prefix="/api/ledger", ...)`:

```python
@router.post("/ping", response_model=PingResponse)
async def ping(req: PingRequest):
  return PingResponse(ok=True, echo=req.message)
```

Mẹo: Sử dụng Dependency Injection có sẵn (ví dụ: `Depends(get_hierarchy_manager)`) nếu endpoint cần truy cập hệ thống chuỗi.

## Bước 3: Khởi chạy Server và Kiểm thử Nhanh

```bash
python -m hierachain.api.server
```

Mở `http://localhost:2661/docs` để thử nghiệm trên Swagger UI hoặc sử dụng `curl`:

```bash
curl -s -X POST http://localhost:2661/api/ledger/ping \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

Nếu xác thực API Key được bật (môi trường production), hãy thêm header tương ứng với `settings.API_KEY_NAME`:

```bash
-H 'X-API-Key: <your-key>'
```

## Bước 4: Liên kết Tài liệu

* Cập nhật `docs/mkdocs.yml` để thêm hướng dẫn này vào mục Hướng dẫn (nếu chưa có).
* Liên kết chéo từ trang Module API / Tham chiếu.

## Ghi chú Mở rộng

* Sử dụng tên đường dẫn, tham số và response model rõ ràng.
* Xử lý lỗi bằng `HTTPException` (400/404/500) với thông điệp minh bạch.
* Viết test case (`pytest`) nếu endpoint chứa logic quan trọng.

## Tài liệu Liên quan

* API Module: [API](../modules/api.md)
* API Ledger Reference: [API Ledger](../reference/api-ledger.md)
* Cấu hình: [Config](../reference/config.md)
