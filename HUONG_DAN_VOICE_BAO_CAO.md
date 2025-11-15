# Hướng dẫn Sử dụng Tính năng Báo cáo bằng Giọng nói

## Giới thiệu

Bot hiện hỗ trợ **2 loại yêu cầu qua voice message**:
1. 🎤 **Ghi nhận giao dịch** - Nói về giao dịch để lưu vào sổ
2. 📊 **Yêu cầu báo cáo** - Nói để xem báo cáo thu chi

## Cách sử dụng

### 1. Ghi nhận Giao dịch (như trước)

**Cách nói**:
- "Mua cafe năm mươi nghìn đồng"
- "Chuyển khoản hai trăm nghìn cho mẹ"
- "Ăn trưa ba mươi lăm nghìn"

**Kết quả**: Bot sẽ lưu giao dịch vào database và gửi xác nhận.

### 2. Yêu cầu Báo cáo ✨ MỚI

**Cách nói**:

#### Báo cáo tháng này:
- "Tổng hợp tháng này"
- "Báo cáo tháng này"
- "Xem chi tiêu tháng này"
- "Cho tôi xem tổng hợp tháng này"

#### Báo cáo tháng cụ thể:
- "Tổng hợp tháng mười một"
- "Báo cáo tháng 11"
- "Xem chi tiêu tháng mười một"

#### Báo cáo tháng trước:
- "Tổng hợp tháng trước"
- "Báo cáo tháng trước"

#### Báo cáo theo loại (thu/chi):
- "Tổng chi tháng này"
- "Tổng thu tháng này"
- "Báo cáo chi tiêu tháng mười một"
- "Báo cáo thu nhập tháng trước"

**Kết quả**: Bot sẽ gửi báo cáo chi tiết với:
- Tổng thu/chi
- Số giao dịch
- Danh mục chi tiêu nhiều nhất
- Tỉ lệ tiết kiệm
- Gợi ý tiết kiệm

## Ví dụ Thực tế

### Ví dụ 1: Xem báo cáo tháng này

**Bạn**: 🎤 *Gửi voice* "Tổng hợp chi tiêu tháng này"

**Bot**: 
```
🔊 Đã nhận file — đang xử lí ở background. 
Bạn sẽ nhận thông báo khi hoàn tất.
```

**Bot** *(sau 3-5 giây)*:
```
🧾 [BÁO CÁO THU CHI CÁ NHÂN]
📅 Thời gian báo cáo:

Từ: 2025-11-01
Đến: 2025-11-13

💰 Tổng hợp tài chính
Tổng thu:       24,000,000 VND
Tổng chi:       20,262,000 VND
Chênh lệch:     3,738,000 VND

📂 Cơ cấu chi tiêu
Số lượng giao dịch: 9
Danh mục chi tiêu nhiều nhất: Mua sắm
Tỉ lệ tiết kiệm: 15%
Trung bình chi/ngày: 1,558,615 VND

📊 Gợi ý chi tiêu
• Xem xét lại các khoản chi cho mua sắm...
• Thiết lập ngân sách cụ thể...
```

### Ví dụ 2: Ghi nhận giao dịch

**Bạn**: 🎤 *Gửi voice* "Mua cafe năm mươi nghìn đồng"

**Bot**:
```
🔊 Đã nhận file — đang xử lí ở background.
```

**Bot** *(sau 2-4 giây)*:
```
✅ Đã lưu giao dịch:
📅 Ngày: 2025-11-13
🏪 Merchant: Cafe
📂 Danh mục: Ăn uống
💰 Số tiền: 50,000 VND
📝 Loại: Chi tiêu
```

### Ví dụ 3: Yêu cầu kép (MỚI) ✨

**Bạn**: 🎤 *Gửi voice* "Mua cafe năm mươi nghìn và cho tôi xem tổng hợp tháng này"

**Bot**:
```
🔊 Đã nhận file — đang xử lí ở background.
```

**Bot** *(sau 1 giây)*:
```
📝 Tôi nghe thấy cả giao dịch VÀ yêu cầu báo cáo. 
Tôi sẽ xử lý cả hai nhé!
```

**Bot** *(sau 2 giây)*:
```
✅ Giao dịch:
📅 Ngày: 2025-11-13
🏪 Merchant: Cafe
💰 Số tiền: 50,000 VND
```

**Bot** *(sau 3 giây)*:
```
🧾 [BÁO CÁO THU CHI CÁ NHÂN]
📅 Thời gian báo cáo:
Từ: 2025-11-01
Đến: 2025-11-13
...
```

### Ví dụ 4: Bot không hiểu rõ

**Bạn**: 🎤 *Gửi voice* "Ừ" *(quá ngắn)*

**Bot**:
```
🤔 Tôi không nghe rõ. Bạn có thể nói lại được không?

Gợi ý:
• Nói rõ ràng hơn
• Ghi âm ở nơi yên tĩnh
• Hoặc gõ text thay vì voice
```

### Ví dụ 5: Intent không rõ

**Bạn**: 🎤 *Gửi voice* "Hôm nay trời đẹp quá"

**Bot**:
```
🤔 Tôi không chắc bạn muốn làm gì. Bạn muốn:

1️⃣ Ghi nhận giao dịch? (Nói: 'Mua cafe 50k')
2️⃣ Xem báo cáo? (Nói: 'Tổng hợp tháng này')

Hoặc gõ text cho chính xác hơn!
```

## Lưu ý Quan trọng

### ✅ Nên làm

1. **Nói rõ ràng**: Phát âm rõ ràng, không quá nhanh
2. **Môi trường yên tĩnh**: Ghi âm ở nơi ít ồn
3. **Sử dụng từ khóa**: Dùng "tổng hợp", "báo cáo", "tháng này"...
4. **Ngắn gọn**: Câu ngắn, súc tích (5-10 từ)

### ❌ Tránh làm

1. **Nói quá nhanh**: Bot có thể không hiểu
2. **Nhiều yêu cầu cùng lúc**: Ví dụ "Mua cafe 50k VÀ cho tôi xem báo cáo"
3. **Âm thanh kém**: Quá ồn, quá nhỏ
4. **Câu quá dài**: Khó transcribe chính xác

## Xử lý Lỗi

### Lỗi 1: Bot không hiểu

**Thông báo**:
```
❌ Xử lí không thành công. Vui lòng thử lại.
```

**Giải pháp**:
- Ghi âm lại ở nơi yên tĩnh hơn
- Nói rõ ràng hơn
- Kiểm tra micro điện thoại

### Lỗi 2: Không hiểu yêu cầu báo cáo

**Thông báo**:
```
Không thể hiểu yêu cầu báo cáo. Vui lòng nói rõ hơn, ví dụ:
• 'Tổng hợp tháng này'
• 'Báo cáo chi tiêu tháng 11'
• 'Xem tổng thu tháng trước'
```

**Giải pháp**:
- Sử dụng một trong các mẫu câu gợi ý
- Nói rõ "tháng này", "tháng trước", hoặc "tháng [số]"

### Lỗi 3: Không có dữ liệu

**Thông báo**:
```
Lỗi khi truy vấn dữ liệu
```

**Giải pháp**:
- Kiểm tra kết nối database
- Thử lại sau vài giây

## Mẹo Sử dụng

### Mẹo 1: Nói tự nhiên
Không cần nói quá cứng nhắc. Bot hiểu nhiều cách nói:
- ✅ "Tổng hợp tháng này"
- ✅ "Cho tôi xem tổng hợp tháng này"
- ✅ "Xem chi tiêu tháng này"

### Mẹo 2: Chỉ định loại báo cáo
Nếu chỉ muốn xem thu hoặc chi:
- "Tổng **chi** tháng này" → Chỉ xem chi tiêu
- "Tổng **thu** tháng này" → Chỉ xem thu nhập

### Mẹo 3: Ghi âm ngắn
Câu ngắn dễ hiểu hơn:
- ✅ "Báo cáo tháng này" (4 từ)
- ❌ "Cho tôi xem báo cáo chi tiêu và thu nhập của tháng này nhé" (13 từ)

### Mẹo 4: Kiểm tra kết quả
Sau khi gửi voice, đợi 3-5 giây để bot xử lý.

## Câu hỏi Thường gặp

### Q1: Bot có hiểu giọng miền Nam/Bắc/Trung không?
**A**: Có! PhoWhisper được train với nhiều giọng Việt Nam.

### Q2: Tôi có thể nói tiếng Anh không?
**A**: Không nên. Bot được tối ưu cho tiếng Việt.

### Q3: Mất bao lâu để xử lý?
**A**: 
- Giao dịch: 2-4 giây
- Báo cáo: 3-5 giây

### Q4: Bot có lưu file âm thanh không?
**A**: Không. File được xóa ngay sau khi xử lý xong.

### Q5: Tôi có thể yêu cầu báo cáo nhiều tháng không?
**A**: Hiện tại chưa hỗ trợ. Chỉ hỗ trợ:
- Tháng này
- Tháng trước
- Tháng cụ thể (ví dụ: tháng 11)

### Q6: Nếu tôi nói cả giao dịch VÀ báo cáo?
**A**: Bot sẽ xử lý CẢ HAI! 
- Ví dụ: "Mua cafe 50k và cho tôi xem tổng hợp tháng này"
- Bot sẽ: Lưu giao dịch TRƯỚC → Sau đó gửi báo cáo

### Q7: Nếu bot không hiểu?
**A**: Bot sẽ hỏi lại bạn với gợi ý cụ thể:
- Transcription quá ngắn → Yêu cầu nói lại
- Không hiểu giao dịch → Gợi ý cách nói
- Intent không rõ → Hỏi muốn làm gì

## So sánh với Text

| Tính năng | Voice | Text |
|-----------|-------|------|
| Tốc độ nhập | ⚡⚡⚡ Nhanh | ⚡⚡ Trung bình |
| Độ chính xác | ⚡⚡ Tốt | ⚡⚡⚡ Rất tốt |
| Tiện lợi | ⚡⚡⚡ Rất tiện | ⚡⚡ Tiện |
| Môi trường | Cần yên tĩnh | Mọi nơi |
| Thời gian xử lý | 3-5s | 1-2s |

**Khuyến nghị**: 
- Dùng **Voice** khi: Đang di chuyển, không tiện gõ
- Dùng **Text** khi: Cần chính xác 100%, môi trường ồn

## Tổng kết

✅ Voice message giờ hỗ trợ cả **giao dịch** và **báo cáo**  
✅ Nói tự nhiên, bot sẽ tự phân loại  
✅ Xử lý nhanh trong 3-5 giây  
✅ Hỗ trợ nhiều cách nói khác nhau  

**Thử ngay**: Gửi voice "Tổng hợp tháng này" để xem báo cáo! 🎤

---

*Cập nhật: 13/11/2025*  
*Phiên bản: 2.0.0*
