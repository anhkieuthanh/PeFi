# Test Scripts

Các script test để kiểm tra chức năng của bot.

## 1. test_gemini.py - Quick Gemini API Test

Test nhanh để kiểm tra Gemini API có hoạt động không.

### Chạy:
```bash
python3 test_gemini.py
```

### Kiểm tra:
- ✅ Configuration (TOKEN, API keys)
- ✅ Vision model config
- ✅ Text processing với Gemini API (thực tế gọi API)

### Khi nào dùng:
- Kiểm tra nhanh Gemini API có hoạt động không
- Debug vấn đề với JSON parsing
- Xác minh prompt đang hoạt động đúng

---

## 2. test_bot.py - Full Bot Test Suite

Test đầy đủ tất cả các chức năng của bot.

### Chạy:
```bash
python3 test_bot.py
```

### Kiểm tra:
- ✅ Configuration loading
- ✅ Text processing với nhiều test cases
- ✅ Database operations (add_bill, create_user, get_user)
- ✅ Image processing from URL
- ✅ JSON parsing robustness

### Khi nào dùng:
- Kiểm tra toàn bộ hệ thống trước khi deploy
- Sau khi sửa code, đảm bảo không làm hỏng gì
- Test database connectivity

---

## Ví dụ Output

### test_gemini.py (thành công):
```
🧪 Quick Gemini API Test

============================================================
TEST: Configuration
============================================================

✓ TOKEN: ********************AAG0NeGdCd
✓ GEMINI_API_KEY: ******************************SyBT0On65r
✓ DATABASE_URL: SET
✓ Text model: gemini-2.5-flash
✓ Vision model: gemini-2.5-flash

✅ Configuration successful!

============================================================
TEST: Gemini Vision Model (Config Only)
============================================================

✓ Model loaded: gemini-2.5-flash
✓ Prompt loaded: 1234 characters
✓ Prompt preview: You are an advanced AI data extractor...

✅ Vision model configuration successful!

============================================================
TEST: Gemini Text Model
============================================================

Input: Cafe Highland 55000 vnd ngay 10/10

Processing...

Result:
  merchant_name: Highland Coffee
  total_amount: 55000
  bill_date: 2025-10-10
  category_name: Ăn uống
  category_type: 0
  note: Cafe Highland
  user_id: 2

✅ Text processing successful!

============================================================
SUMMARY
============================================================
✅ Configuration
✅ Vision Model Config
✅ Text Processing

Total: 3/3 tests passed

🎉 All tests passed!
```

### test_bot.py (thành công):
```
============================================================
BOT FUNCTIONALITY TEST SUITE
============================================================

============================================================
TEST 1: Configuration
============================================================
✓ Config loaded successfully
  - TOKEN: **********
  - UPLOAD_DIR: uploads
  - GEMINI_API_KEY: ********************
✓ Text model: gemini-2.5-flash
✓ Vision model: gemini-2.5-flash

...

============================================================
TEST SUMMARY
============================================================
✓ PASSED: config
✓ PASSED: text_processing
✓ PASSED: database
✓ PASSED: image_processing
✓ PASSED: json_parsing

Total: 5/5 tests passed

🎉 All tests passed!
```

---

## Troubleshooting

### ImportError: No module named 'config'
→ Đảm bảo chạy từ thư mục project root:
```bash
cd /Users/atif/Public/Code\ GenAI/01.Project_01
python3 test_gemini.py
```

### Database connection failed
→ Kiểm tra DATABASE_URL trong config.yaml hoặc .env

### Gemini API errors
→ Kiểm tra:
- GEMINI_API_KEY có đúng không
- Có internet connection không
- API quota còn không

### Test case failed với "Invalid"
→ Gemini không parse được text
- Xem log để biết Gemini trả về gì
- Có thể cần điều chỉnh prompt
- Kiểm tra model name có đúng không (gemini-1.5-flash hoặc gemini-2.5-flash)

---

## Development Workflow

1. **Sau khi thay đổi code:**
   ```bash
   python3 test_gemini.py  # Quick test
   ```

2. **Trước khi commit:**
   ```bash
   python3 test_bot.py     # Full test
   ```

3. **Sau khi deploy:**
   ```bash
   cd src
   python3 bot.py          # Run actual bot
   ```
   Gửi tin nhắn test qua Telegram

---

## Notes

- Test scripts không cần database để chạy test_gemini.py
- test_bot.py cần database connection để test database operations
- Cả hai đều cần GEMINI_API_KEY hợp lệ
- Test scripts tự động load config từ config.yaml và .env
