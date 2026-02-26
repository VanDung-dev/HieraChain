---
title: "Quy trình phát hành"
description: "Quy trình phát hành phiên bản và tài liệu: versioning bằng setuptools_scm, chuẩn bị gói, ghi chú phát hành."
icon: material/rocket
---

# Quy trình phát hành

## Versioning

* Dùng `setuptools_scm` (xem `pyproject.toml`) để suy luận phiên bản từ thẻ Git.
* Tạo thẻ theo mẫu: `vX.Y.Z` hoặc `vX.Y.Z.devN` cho bản phát triển.

## Chuẩn bị phát hành

1. Đảm bảo test xanh: `pytest -v`.
2. Soát tài liệu: liên kết/chỉ mục/nav cập nhật.
3. Cập nhật `docs/vi/changelog.md` với nội dung phát hành.

## Đóng gói

```bash
python -m build
twine check dist/*
# (tuỳ chọn) twine upload dist/*
```

## Phát hành tài liệu

* Build site tĩnh bằng MkDocs (thực hiện sau khi nội dung ổn định).
* CI (sau): build preview trên PR, publish khi merge `main`.

## Ghi chú phát hành

* Tóm tắt thay đổi chính của mã và tài liệu.
* Link tới các PR liên quan; liệt kê điểm phá vỡ (breaking changes) nếu có.

---

??? info "Thông tin kỹ thuật bổ sung (Metadata)"

    **FACT**

    * `setuptools_scm` được cấu hình trong `pyproject.toml`.
    * Dự án dùng nhiều giấy phép (Apache-2.0 hoặc MIT) — xem README/Licenses.

    **DECISION**

    * Chỉ publish tài liệu sau khi docs/vi ổn định và qua review.

    **ASSUMPTION**

    * Có quyền push thẻ và quyền publish gói (nếu áp dụng).

    **INVARIANT**

    * Tag phiên bản phải khớp nội dung; không cập nhật docs sau khi đã gắn thẻ nếu chưa tăng phiên bản.

    **EDGE CASES**

    * Chênh lệch thẻ/commit gây sai phiên bản suy luận → kiểm tra lại lịch sử Git trước khi build.
