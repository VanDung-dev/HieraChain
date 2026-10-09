---
title: "Quy trình phát hành"
description: "Chuẩn bị phát hành, quản lý phiên bản từ hierachain/config/version.py, đóng gói và build tài liệu."
icon: material/rocket
---

# Quy trình phát hành

## Quản lý phiên bản

`pyproject.toml` đọc `hierachain.config.version.__version__`, được tính từ tuple `VERSION` trong `hierachain/config/version.py`. Chỉ tạo Git tag không đổi version package; dự án không dùng `setuptools_scm`.

## Chuẩn bị và đóng gói

1. Chạy từng file test liên quan, cùng các kiểm tra CI bắt buộc về static analysis và backend thật.
2. Đồng bộ tài liệu Anh/Việt tương ứng. Changelog mô tả thay đổi thư viện cốt lõi, không ghi riêng chỉnh sửa tài liệu.
3. Cập nhật tuple version Python và tag phát hành thống nhất.

```bash
uv build
python -m twine check dist/*
```

Xuất bản là bước phát hành riêng. Xem `.github/workflows/` về yêu cầu workflow đã cấu hình.

## Tài liệu

Build bằng Zensical, tiếng Anh trước và tiếng Việt sau:

```bash
zensical build -f zensical.toml
zensical build -f zensical.vi.toml
```

`.github/workflows/docs.yml` build cả hai ngôn ngữ với pull request khớp bộ lọc và deploy GitHub Pages khi push khớp bộ lọc lên `main`.
