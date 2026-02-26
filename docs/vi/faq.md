---
title: "Câu hỏi thường gặp"
description: "FAQ về cài đặt, cấu hình, API, bảo mật, hiệu năng và lưu trữ cho HieraChain."
icon: material/frequently-asked-questions
---

# Câu hỏi thường gặp (FAQ)

!!! question "Mặc định API chạy ở cổng nào?"
    Mặc định 2661 (xem `hierachain/config/settings.py`).

!!! question "Làm sao bật xác thực API key?"
    Đặt `HRC_AUTH_ENABLED=true` và gửi header `X-API-Key` (hoặc tên tuỳ biến theo `API_KEY_NAME`).

!!! question "Khác nhau giữa Main Chain và Sub‑Chain?"
    Main Chain lưu proof; Sub‑Chain lưu dữ liệu sự kiện chi tiết theo domain.

!!! question "Tại sao event không có timestamp client gửi?"
    Server sinh timestamp tại thời điểm nhận; giúp thống nhất nguồn thời gian.

!!! question "`details` phải có kiểu gì?"
    Map<string,string>; giá trị phi chuỗi sẽ được chuyển sang chuỗi.

!!! question "Tạo Sub‑Chain báo lỗi tên không hợp lệ?"
    Tên chỉ chứa `[a-zA-Z0-9_\-]` (xem kiểm tra trong `api/v1/endpoints.py`).

!!! question "Vì sao submit proof mà block của Sub‑Chain vẫn chưa thấy?"
    Kiểm tra điều kiện finalize block, thời gian/lô sự kiện; thử gọi lại submit hoặc xem log.

!!! question "Hiệu năng thấp, hay 503?"
    Xem `ResourceGuardMiddleware`, bật cache nâng cao, tối ưu batch size, kiểm tra CPU/RAM.

!!! question "Có API v2 không và dùng để làm gì?"
    Có; quản lý channel, private data, contracts, organizations. Xem `docs/vi/reference/api-v2.md`.

!!! question "CLI ở đâu và dùng thế nào?"
    Lệnh `hrc` (đăng ký trong `pyproject.toml`). Xem `docs/vi/modules/cli.md`.

!!! question "Có thể dùng Redis/SQLite làm backend?"
    Có; cấu hình qua `DEFAULT_STORAGE_BACKEND`, `DATABASE_URL`, `REDIS_*`.

!!! question "Làm thế nào để đóng góp mã nguồn?"
    Xem `docs/vi/dev/contributing.md`.

!!! question "Test được bố trí và chạy như thế nào?"
    Markers/paths trong `pyproject.toml`. Xem `docs/vi/dev/testing.md`.

!!! question "Quy trình phát hành?"
    Dựa trên `setuptools_scm`; xem `docs/vi/dev/release-process.md`.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Tham số/cấu hình lấy từ `hierachain/config/settings.py`; API tại `hierachain/api/*`.

    **DECISION**

    * Trả lời ngắn gọn, liên kết chi tiết tới trang chuyên đề.

    **ASSUMPTION**

    * Độc giả quen dùng curl/Python cơ bản.

    **INVARIANT**

    * FAQ không được mâu thuẫn với tài liệu và mã nguồn.

    **EDGE CASES**

    * Câu trả lời có thể thay đổi theo phiên bản; luôn tham chiếu mã/tài liệu tương ứng phiên bản đang chạy.
