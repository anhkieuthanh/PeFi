# PeFi

Quản lý tài chính cá nhân, phân tích giao dịch, dashboard trực quan.

## Yêu cầu hệ thống
- Python >= 3.10
- PostgreSQL
- pip (Python package manager)

## Cài đặt nhanh

1. **Clone mã nguồn**
```bash
git clone https://github.com/anhkieuthanh/PeFi.git
cd PeFi
```

2. **Cài đặt Python package**
```bash
pip install -r requirements.txt
```

3. **Cấu hình kết nối database**
- Tạo file `config.yaml` (hoặc sửa `config.sample.yaml`):
```yaml
database:
  url: postgresql://username:password@localhost:5432/ten_db
```
- Tạo database và import schema:
```bash
psql -U <username> -d <ten_db> -f database/schema.sql
```

4. **Chạy server**
```bash
cd database
python run.py
```
- Mặc định chạy tại http://127.0.0.1:5001/

5. **Chạy bot Telegram (nếu dùng)**
- Sửa `src/config.yaml` với token bot Telegram.
- Chạy bot:
```bash
cd src
python bot.py
```

## Dashboard
- Truy cập http://127.0.0.1:5001/ để xem dashboard, lọc giao dịch, phân trang, xuất báo cáo.

## Troubleshooting
- Nếu lỗi kết nối DB: kiểm tra lại `config.yaml` và database đã tạo đúng schema chưa.
- Nếu lỗi cài package: kiểm tra phiên bản Python, pip, và quyền truy cập.

## Đóng góp
- Fork, tạo pull request hoặc liên hệ qua GitHub.

## License
MIT
