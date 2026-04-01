---
title: "Hướng dẫn đóng góp"
description: "Hướng dẫn đóng góp cho HieraChain: quy trình Fork & Pull, chuẩn mã nguồn, kiểm thử và quy tắc ứng xử."
icon: material/account-group
---

# Hướng dẫn đóng góp

!!! note "Lưu ý"
    Tài liệu này là hướng dẫn chi tiết dành cho nhà phát triển. Để xem quy định đóng góp tóm tắt (bản gốc tiếng Anh), vui lòng xem **[CONTRIBUTING.md](https://github.com/VanDung-dev/HieraChain/blob/main/CONTRIBUTING.md)**.

Cảm ơn bạn đã quan tâm đóng góp cho HieraChain! Chúng tôi hoan nghênh mọi đóng góp, từ báo lỗi, đề xuất tính năng, sửa đổi tài liệu đến gửi mã nguồn.

## Quy trình đóng góp (Contribution Workflow)

Chúng tôi sử dụng quy trình **Fork & Pull** tiêu chuẩn:

1. **Fork** dự án về tài khoản GitHub của bạn.
2. **Clone** bản fork về máy cá nhân:

    ```bash
    git clone https://github.com/VanDung-dev/HieraChain.git
    cd HieraChain
    ```

3. Tạo **Branch** mới cho tính năng hoặc sửa lỗi của bạn:

    ```bash
    git checkout -b feature/ten-tinh-nang-moi
    # hoặc
    git checkout -b fix/loi-can-sua
    ```

4. Thay đổi code và **Commit**. Chúng tôi khuyến khích tuân thủ [Conventional Commits](https://www.conventionalcommits.org/):

    * `feat: ...`: Tính năng mới
    * `fix: ...`: Sửa lỗi
    * `docs: ...`: Thay đổi tài liệu
    * `style: ...`: Định dạng code (không ảnh hưởng logic)
    * `refactor: ...`: Tái cấu trúc mã
    * `test: ...`: Thêm hoặc sửa test

5. **Push** branch lên fork của bạn.
6. Tạo **Pull Request (PR)** từ branch của bạn vào branch `main` của repo gốc HieraChain.

## Môi trường phát triển

Để thiết lập môi trường, cài đặt dependencies và chạy test, vui lòng xem hướng dẫn chi tiết tại: **[Cài đặt](../getting-started/install.md)** hoặc **[Kiểm thử](testing.md)**.

## Tiêu chuẩn mã nguồn (Coding Standards)

* Tuân thủ tiêu chuẩn **PEP 8**.
* Đảm bảo mã vượt qua các kiểm tra phân tích tĩnh (static analysis) trong thư mục `scripts/`.
* Mã mới phải có **Type Hints** đầy đủ (Python >= 3.10).

## Quy tắc cấm (Forbidden Patterns)

Để đảm bảo tính nhất quán và triết lý của HieraChain, các nhà phát triển **TUYỆT ĐỐI KHÔNG**:

* ❌ **Sử dụng thuật ngữ tiền điện tử**: Không dùng các từ như `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `amount`, `fee`. Thay vào đó, hãy dùng `event`, `entity_id`, `details`.
* ❌ **Sử dụng `print()`**: Luôn sử dụng `logging.getLogger(__name__)`.
* ❌ **Truy cập DB trực tiếp**: Không gọi trực tiếp `sqlite3` hay `redis` bên ngoài thư mục `adapters/storage/`.
* ❌ **Bỏ qua Journal**: Không bỏ qua bước ghi `TransactionJournal` khi thiết lập luồng ordering mới.
* ❌ **Lưu secret trong code**: Luôn sử dụng biến môi trường hoặc Secret Manager.

## Kiểm thử (Testing)

HieraChain duy trì tiêu chuẩn cao về chất lượng mã. Mọi đóng góp đều phải vượt qua các bài kiểm tra tự động.

### Cấu trúc bài test

* `tests/unit`: Unit tests, kiểm tra từng hàm/lớp riêng lẻ.
* `tests/integration`: Integration tests, kiểm tra tương tác giữa các thành phần.
* `tests/scenarios`: Scenario tests, mô phỏng luồng nghiệp vụ thực tế.

### Chạy test

Bạn có thể chạy toàn bộ test bằng lệnh:

```bash
python -m pytest tests -v
```

Để chạy từng phần hoặc tìm hiểu thêm, vui lòng xem chi tiết tại **[Kiểm thử](testing.md)**.

### Yêu cầu đóng góp

1. **Viết test mới**: Nếu bạn thêm tính năng mới, hãy viết test case tương ứng (thường trong `tests/unit`).
2. **Không làm hỏng test cũ**: Đảm bảo mã của bạn không gây lỗi cho các test hiện có.
3. **Docs**: Docs liên quan phải được cập nhật và không bị gãy link.

## Báo lỗi và Đề xuất

Sử dụng tab **Issues** trên GitHub để báo lỗi hoặc yêu cầu tính năng.

Khi báo lỗi, vui lòng cung cấp:

1. Mô tả chi tiết lỗi.
2. Các bước tái hiện.
3. Môi trường (Hệ điều hành, phiên bản Python, logs lỗi...).

## Chính sách bảo mật (Security Policy)

Nếu bạn phát hiện vấn đề bảo mật trong HieraChain, vui lòng **KHÔNG** báo cáo qua Issues công khai.

### Quy trình báo cáo

Hãy gửi báo cáo bảo mật bí mật (confidential security bug) thông qua [trang Security Advisories](https://github.com/VanDung-dev/HieraChain/security). Xem hướng dẫn chi tiết về [báo cáo lỗ hổng riêng tư](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) của GitHub.

### Quy trình xử lý

Khi nhận được báo cáo, chúng tôi sẽ:

1. Xác nhận vấn đề và đánh giá mức độ nghiêm trọng.
2. Phát triển bản vá lỗi trong thời gian sớm nhất.
3. Phát hành bản vá và công bố thông báo bảo mật (security bulletin), bao gồm việc ghi nhận công lao của người phát hiện (nếu có).

### Đóng góp sửa lỗi bảo mật

Nếu bạn muốn đóng góp bản vá bảo mật, vui lòng phối hợp qua quy trình Security Advisories trước khi tạo Pull Request để đảm bảo an toàn cho người dùng.

## Quy tắc ứng xử (Code of Conduct)

Chúng tôi cam kết xây dựng môi trường mở, thân thiện và tôn trọng. Vui lòng giữ thái độ chuyên nghiệp và lịch sự trong mọi tương tác.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * Ngôn ngữ: Python >= 3.10.
    * Script CLI: `hrc`.
    * Tài liệu tham chiếu: `README.md`, `pyproject.toml`.

    **DECISION**

    * Tiêu chuẩn tài liệu 5 khối (FACT/DECISION/ASSUMPTION/INVARIANT/EDGE CASES).
    * Commit message theo cấu trúc `scope: summary`.

    **ASSUMPTION**

    * Contributor cài được môi trường Python 3.10+ và các công cụ dev cơ bản.

    **INVARIANT**

    * PR không làm gãy build/test hiện có.
    * Tài liệu phải bám sát mã nguồn hiện tại.

    **EDGE CASES**

    * PR quá lớn hoặc chứa nhiều thay đổi không liên quan sẽ bị yêu cầu tách nhỏ.
