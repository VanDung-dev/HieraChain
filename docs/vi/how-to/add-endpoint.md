---
title: "How-to: Thêm endpoint API v1"
description: "Các bước thêm một endpoint mới vào API v1, wiring schema/handler và kiểm thử nhanh bằng curl."
icon: material/plus-network
---

# Thêm endpoint mới vào API v1

## Mục tiêu

Hướng dẫn từng bước để thêm một endpoint mới vào FastAPI router của HieraChain (phiên bản v1), bao gồm định nghĩa schema Pydantic, viết handler, cập nhật router và kiểm thử nhanh bằng `curl`.

## Bước 1: Chuẩn bị schema (tuỳ chọn)

* Mở `hierachain/api/v1/schemas.py`.
* Thêm lớp Pydantic nếu endpoint cần payload mới, ví dụ:

```pycon
class PingRequest(BaseModel):
  message: str

class PingResponse(BaseModel):
  ok: bool
  echo: str
```

## Bước 2: Thêm handler trong router

* Mở `hierachain/api/v1/endpoints.py`.
* Import schema (nếu có) và thêm route vào `APIRouter(prefix="/api/v1", ...)`.

Ví dụ (mô tả):

```python
@router.post("/ping", response_model=PingResponse)
async def ping(req: PingRequest):
  return PingResponse(ok=True, echo=req.message)
```

Gợi ý: dùng DI sẵn có (ví dụ `Depends(get_hierarchy_manager)`) nếu endpoint cần truy cập hệ thống chuỗi.

## Bước 3: Chạy server và kiểm thử nhanh

```bash
python -m hierachain.api.server
```

Mở `http://localhost:2661/docs` để thử trên Swagger UI hoặc dùng `curl`:

```bash
curl -s -X POST http://localhost:2661/api/v1/ping \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

Nếu bật xác thực API key (production), thêm header theo `settings.API_KEY_NAME`:

```bash
-H 'X-API-Key: <your-key>'
```

## Bước 4: Liên kết tài liệu

* Cập nhật `docs/mkdocs.yml` để bổ sung hướng dẫn này vào mục Hướng dẫn (nếu chưa có).
* Liên kết chéo từ trang API module/Reference.

## Lưu ý mở rộng

* Đặt tên đường dẫn, tham số, và response model rõ ràng.
* Xử lý lỗi với `HTTPException` (400/404/500) và thông điệp minh bạch.
* Viết test (pytest) nếu endpoint có logic quan trọng.

## Liên quan

* API module: [API](../modules/api.md)
* Reference API v1: [API v1](../reference/api-v1.md)
* Config: [Config](../reference/config.md)

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Router chính nằm ở `hierachain/api/v1/endpoints.py`; schema Pydantic ở `hierachain/api/v1/schemas.py`.
    * Server khởi chạy bằng `python -m hierachain.api.server` (mặc định cổng 2661).

    **DECISION**

    * Tuân thủ mẫu DI sẵn có (lazy singleton `HierarchyManager`/`EntityTracer`) để truy cập tài nguyên hệ thống.
    * Tài liệu hướng dẫn ưu tiên ví dụ tối thiểu và kiểm thử `curl`.

    **ASSUMPTION**

    * Môi trường đã cài đặt đầy đủ dependencies và cấu hình cổng mặc định.
    * Nếu bật AUTH, client sẽ gửi API key đúng vị trí (header/query theo cấu hình).

    **INVARIANT**

    * Endpoint mới cần trả về JSON hợp lệ và mô tả qua schema khi phù hợp.
    * Không phá vỡ URL hiện hữu; tuân thủ prefix `/api/v1`.

    **EDGE CASES**

    * Thiếu schema hoặc khai báo sai `response_model` → tài liệu OpenAPI sai, dễ gây nhầm lẫn client.
    * Quên thêm API key khi AUTH bật → 401/403.
