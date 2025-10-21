# PeFi - Personal Finance Bot

Telegram bot quản lý tài chính cá nhân với AI, tự động phân tích hóa đơn và giao dịch bằng Google Gemini.

## ✨ Tính năng

- 📸 **Chụp hóa đơn** - Gửi ảnh hóa đơn qua Telegram, bot tự động đọc và lưu thông tin
- 💬 **Nhập text** - Gõ giao dịch dạng text (VD: "Cafe Highland 55k ngày 10/10")
- 🤖 **AI Vision** - Sử dụng Google Gemini để OCR và phân tích hóa đơn
- 💾 **Lưu trữ PostgreSQL** - Tất cả giao dịch được lưu vào database
- 📊 **Phân loại tự động** - AI tự động phân loại chi tiêu/thu nhập

## 🎯 Kiến trúc

```
Telegram Bot → Gemini AI (OCR/Parse) → PostgreSQL
```

- **Telegram Bot**: Interface chính để nhận ảnh/text
- **Google Gemini**: Vision model phân tích hóa đơn, Text model parse text
- **Direct DB**: Lưu trực tiếp vào PostgreSQL (không qua API)

## 🔧 Yêu cầu hệ thống

- Python >= 3.13
- PostgreSQL database
- Telegram Bot Token
- Google Gemini API Key

## 📦 Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/anhkieuthanh/PeFi.git
cd PeFi
```

### 2. Tạo virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# hoặc: venv\Scripts\activate  # Windows
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Cấu hình

Tạo file `config.yaml` (hoặc copy từ `config.sample.yaml`):

```yaml
telegram:
  token: "YOUR_TELEGRAM_BOT_TOKEN"

uploads:
  dir: "uploads"

google:
  gemini_api_key: "YOUR_GEMINI_API_KEY"

database:
  url: "postgresql://user:password@host:port/database"
```

**Lấy API keys:**
- Telegram Bot Token: Tạo bot mới với [@BotFather](https://t.me/botfather)
- Gemini API Key: [Google AI Studio](https://makersuite.google.com/app/apikey)

### 5. Khởi tạo database

```bash
psql -U <username> -d <database_name> -f database/schema.sql
```

### 6. Chạy bot

```bash
cd src
python3 bot.py
```

Bot sẽ bắt đầu chạy và sẵn sàng nhận tin nhắn từ Telegram!

## 🧪 Testing

### Quick test (Gemini API only)

```bash
python3 test_gemini.py
```

Kiểm tra:
- ✅ Configuration
- ✅ Gemini model initialization
- ✅ Vietnamese transaction parsing

### Full test suite

```bash
python3 test_bot.py
```

Kiểm tra:
- ✅ Config loading
- ✅ Text processing (3 test cases)
- ✅ Database operations
- ✅ Image processing
- ✅ JSON parsing robustness

Xem thêm: [TESTING.md](TESTING.md)

## 📝 Sử dụng

### 1. Gửi ảnh hóa đơn

Chụp/gửi ảnh hóa đơn qua Telegram → Bot tự động:
1. Tải và xử lý ảnh
2. Gửi đến Gemini Vision để OCR
3. Parse thông tin (merchant, số tiền, ngày, category)
4. Lưu vào database
5. Reply với thông tin đã lưu

### 2. Gửi text giao dịch

Gõ thông tin giao dịch, ví dụ:
- `Cafe Highland 55000 vnd ngay 10/10`
- `CK 200k cho me`
- `Ting ting +50,000,000 VND tu CONG TY ABC`

Bot sẽ parse và lưu tương tự.

### 3. Danh mục tự động

Bot tự động phân loại vào các category:

**Chi tiêu (type = 0):**
- Ăn uống, Xe cộ, Mua sắm, Học tập, Y tế, Du lịch
- Điện, Nước, Internet, Thuê nhà, Giải trí
- Thú cưng, Dịch vụ, Sửa chữa, Quà tặng

**Thu nhập (type = 1):**
- Lương, Tiền lãi đầu tư, Tiền cho thuê nhà

## 🗂️ Cấu trúc project

```
PeFi/
├── src/                    # Bot source code
│   ├── bot.py             # Main bot entry point
│   ├── config.py          # Configuration loader
│   └── utils/             # Utilities
│       ├── telegram_handlers.py    # Photo/text handlers
│       ├── image_processor.py      # Gemini Vision processing
│       ├── text_processor.py       # Gemini Text processing
│       └── promt.py                # Prompt management
├── database/              # Database layer
│   ├── database.py        # DB connection
│   ├── db_operations.py   # Direct DB operations
│   └── schema.sql         # Database schema
├── prompts/               # AI prompts
│   ├── image_input.txt    # Vision model prompt
│   └── text_input.txt     # Text model prompt
├── test_gemini.py         # Quick API test
├── test_bot.py            # Full test suite
├── requirements.txt       # Python dependencies
├── config.yaml            # Configuration (create from sample)
└── README.md              # This file
```

## 🔍 Troubleshooting

### Bot không nhận tin nhắn
- Kiểm tra `TELEGRAM_BOT_TOKEN` trong `config.yaml`
- Đảm bảo đã `/start` bot trên Telegram
- Kiểm tra bot đang chạy: `ps aux | grep bot.py`

### Gemini trả về "Invalid"
- Kiểm tra `GEMINI_API_KEY` còn quota không
- Xem log để biết Gemini trả về gì: `grep "Gemini.*response" logs`
- Thử test với `python3 test_gemini.py`

### Database connection failed
- Kiểm tra `DATABASE_URL` trong config
- Test connection: `psql <DATABASE_URL>`
- Đảm bảo schema đã được import

### JSON parsing error
- Prompts đã được tối ưu để Gemini trả về JSON
- Có `response_mime_type: "application/json"` trong generation_config
- Code tự động strip markdown code blocks

### Import errors
- Đảm bảo đang ở đúng thư mục khi chạy
- Activate virtual environment: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

## 🚀 Development

### Workflow

1. Thay đổi code
2. Run quick test: `python3 test_gemini.py`
3. Run full test: `python3 test_bot.py`
4. Test thủ công với bot
5. Commit và push

### Update prompts

Prompts trong `prompts/` được load động, sửa file và restart bot là có hiệu lực.

### Add new features

1. Thêm handler trong `src/utils/telegram_handlers.py`
2. Add database operations trong `database/db_operations.py`
3. Update schema nếu cần: `database/schema.sql`
4. Add test cases vào `test_bot.py`

## 📄 Dependencies

- `python-telegram-bot` - Telegram Bot API
- `google-generativeai` - Gemini AI models
- `psycopg2-binary` - PostgreSQL adapter
- `Pillow` - Image processing
- `requests` - HTTP client
- `PyYAML` - Config parser

## 🤝 Contributing

1. Fork repo
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📜 License

MIT License - see LICENSE file for details

## 🙏 Credits

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Google Gemini](https://ai.google.dev/)
- Contributors và community

---

**Note**: Đây là phiên bản bot-only (đã remove Flask web/API layer). Bot giao tiếp trực tiếp với database qua `db_operations.py`.
