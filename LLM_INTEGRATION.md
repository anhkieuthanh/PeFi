# Local LLM Integration

Hướng dẫn sử dụng local LLM với database.

## Tổng quan

Module `llm/llm.py` cung cấp:
- **LocalLLMClient**: Kết nối với local LLM server (OpenAI-compatible API)
- **LLMDatabaseAgent**: Query database bằng natural language
- Parse Vietnamese transaction text
- Generate financial insights

## Setup Local LLM Server

### Option 1: LM Studio (Recommended)

1. Download [LM Studio](https://lmstudio.ai/)
2. Tải model (VD: Llama 3.2, Mistral, Qwen)
3. Start server:
   - Click "Local Server" tab
   - Load model
   - Start server tại port 1234
   - URL: `http://localhost:1234/v1`

### Option 2: Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Tải model
ollama pull llama3.2

# Chạy server
ollama serve
```

URL mặc định: `http://localhost:11434/v1`

### Option 3: Custom OpenAI-compatible server

Bất kỳ server nào support OpenAI API format đều hoạt động.

## Cài đặt

```bash
# Không cần cài thêm package nào, chỉ cần requests
pip install requests
```

## Sử dụng

### 1. Parse Transaction Text

```python
from llm.llm import create_llm_client

client = create_llm_client("http://localhost:1234/v1")

text = "Cafe Highland 55k hôm qua"
result = client.parse_transaction_text(text)

print(result)
# {
#   "merchant_name": "Highland Coffee",
#   "total_amount": 55000,
#   "category_name": "Ăn uống",
#   "category_type": 0,
#   "bill_date": "2025-10-23",
#   "note": "Cafe",
#   "user_id": 2
# }
```

### 2. Natural Language Database Query

```python
from llm.llm import create_llm_db_agent

agent = create_llm_db_agent("http://localhost:1234/v1")

result = agent.natural_language_query("Cho tôi xem 5 giao dịch gần đây")

if result['success']:
    print(f"SQL: {result['sql']}")
    print(f"Data: {result['data']}")
```

### 3. Financial Insights

```python
agent = create_llm_db_agent()

insights = agent.get_spending_insights(user_id=2, days=30)
print(insights)
# LLM sẽ phân tích chi tiêu và đưa ra lời khuyên
```

### 4. Custom Chat Completion

```python
client = create_llm_client()

messages = [
    {"role": "system", "content": "Bạn là trợ lý tài chính"},
    {"role": "user", "content": "Tôi nên tiết kiệm thế nào?"}
]

response = client.chat_completion(messages)
print(response)
```

## Test & Demo

### Test LLM Integration

```bash
python3 test_llm.py
```

Kiểm tra:
- ✅ LLM server connection
- ✅ Chat completion
- ✅ Transaction parsing
- ✅ Natural language query
- ✅ Spending insights

### Run Demo

```bash
python3 demo_llm.py
```

Demos:
1. Parse transaction text
2. Natural language query
3. Financial insights
4. Interactive chat

## Tích hợp vào Telegram Bot

### Option 1: Thay Gemini bằng Local LLM

Sửa `src/utils/text_processor.py`:

```python
from llm.llm import create_llm_client

def parse_text_for_info(raw_text: str) -> Dict[str, Any]:
    # Thay vì dùng Gemini
    # model = config.get_text_model()
    
    # Dùng local LLM
    client = create_llm_client()
    return client.parse_transaction_text(raw_text)
```

### Option 2: Dùng song song Gemini + Local LLM

```python
def parse_text_for_info(raw_text: str) -> Dict[str, Any]:
    try:
        # Try Gemini first
        model = config.get_text_model()
        response = model.generate_content(...)
        return parse_gemini_response(response)
    except Exception:
        # Fallback to local LLM
        client = create_llm_client()
        return client.parse_transaction_text(raw_text)
```

### Option 3: Add new Telegram command

Thêm vào `src/utils/telegram_handlers.py`:

```python
from llm.llm import create_llm_db_agent

async def insights_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /insights command"""
    agent = create_llm_db_agent()
    user_id = get_user_id(update)
    
    insights = agent.get_spending_insights(user_id, days=30)
    await update.message.reply_text(insights)

# Register trong bot.py
application.add_handler(CommandHandler("insights", insights_handler))
```

## Configuration

Thêm vào `config.yaml`:

```yaml
llm:
  base_url: "http://localhost:1234/v1"
  model: "local-model"
  timeout: 60
  enabled: true  # Set false để disable local LLM
```

Load trong `src/config.py`:

```python
LLM_BASE_URL = _get('llm.base_url', default='http://localhost:1234/v1')
LLM_ENABLED = _get('llm.enabled', default=False)
```

## Performance & Cost

### Local LLM
- ✅ **Free**: Không tốn API cost
- ✅ **Privacy**: Dữ liệu không rời máy
- ✅ **No rate limits**: Không bị giới hạn requests
- ⚠️  **Slower**: Tùy hardware (GPU > CPU)
- ⚠️  **Quality**: Tùy model size

### Gemini API
- ✅ **Fast**: Response nhanh
- ✅ **High quality**: Model lớn, accurate
- ⚠️  **Cost**: Tốn API credits
- ⚠️  **Rate limits**: Limited requests/minute
- ⚠️  **Privacy**: Data gửi đến Google

### Recommendation

- **Development**: Dùng local LLM (free, không lo rate limit)
- **Production**: Dùng Gemini (fast, reliable)
- **Hybrid**: Gemini cho critical features, local LLM cho nice-to-have

## Troubleshooting

### LLM server không kết nối được
```
❌ Failed to connect to LLM server
```

**Fix:**
- Kiểm tra server đang chạy: `curl http://localhost:1234/v1/models`
- Đổi port nếu cần: `create_llm_client("http://localhost:11434/v1")`

### Response không phải JSON
```
❌ Failed to parse LLM response as JSON
```

**Fix:**
- Model quá nhỏ → dùng model lớn hơn (3B+ params)
- Prompt chưa rõ → xem log response, adjust prompt
- Thêm temperature=0.1 để deterministic hơn

### SQL injection concern
```
❌ Query không được phép (chỉ SELECT)
```

Module tự động validate và chỉ cho phép SELECT queries.

### Slow responses
```
⏱️  Query takes >10 seconds
```

**Fix:**
- Dùng GPU nếu có
- Giảm max_tokens
- Dùng model nhỏ hơn nhưng fast (1B-3B params)
- Enable quantization trong LM Studio

## Model Recommendations

| Use Case | Model | Size | Speed | Quality |
|----------|-------|------|-------|---------|
| Parse text | Qwen2.5 1.5B | Small | Fast | Good |
| Database query | Llama 3.2 3B | Medium | Medium | Good |
| Insights | Mistral 7B | Large | Slow | Excellent |
| All-in-one | Qwen2.5 7B | Large | Medium | Excellent |

## Examples

Xem file `demo_llm.py` để biết full examples.

## API Reference

### LocalLLMClient

```python
client = LocalLLMClient(base_url, timeout)

# Test connection
client.test_connection() -> bool

# Chat completion
client.chat_completion(messages, model, temperature, max_tokens) -> str

# Parse transaction
client.parse_transaction_text(raw_text) -> Dict
```

### LLMDatabaseAgent

```python
agent = LLMDatabaseAgent(llm_client, db_connection)

# Natural language query
agent.natural_language_query(question) -> Dict

# Get insights
agent.get_spending_insights(user_id, days) -> str
```

## Next Steps

1. Setup local LLM server (LM Studio hoặc Ollama)
2. Run test: `python3 test_llm.py`
3. Try demo: `python3 demo_llm.py`
4. Tích hợp vào bot nếu muốn
5. (Optional) Add `/insights` command vào Telegram bot

---

**Note**: Local LLM là optional feature. Bot vẫn hoạt động bình thường với Gemini nếu không setup local LLM.
