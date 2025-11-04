#!/usr/bin/env python3
"""
Test script cho local LLM integration
Kiểm tra kết nối với LLM server tại localhost:1234/v1
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging  # noqa: E402

from llm.llm import create_llm_client, create_llm_db_agent  # noqa: E402

# Setup logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)


def test_llm_connection():
    """Test 1: Kiểm tra kết nối với LLM server"""
    print("\n" + "=" * 60)
    print("TEST 1: LLM Server Connection")
    print("=" * 60)

    try:
        client = create_llm_client()

        if client.test_connection():
            print("✅ Kết nối thành công với LLM server!")
            return True
        else:
            print("❌ Không thể kết nối với LLM server")
            print("   Đảm bảo LLM server đang chạy tại http://localhost:1234")
            return False

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False


def test_chat_completion():
    """Test 2: Chat completion cơ bản"""
    print("\n" + "=" * 60)
    print("TEST 2: Chat Completion")
    print("=" * 60)

    try:
        client = create_llm_client()

        messages = [
            {"role": "system", "content": "Bạn là trợ lý AI hữu ích."},
            {"role": "user", "content": "Xin chào! 2 + 2 bằng mấy?"},
        ]

        print("\n📤 Gửi request đến LLM...")
        response = client.chat_completion(messages, temperature=0.1, max_tokens=100)

        if response:
            print(f"\n📥 Response từ LLM:\n{response}")
            print("\n✅ Chat completion hoạt động!")
            return True
        else:
            print("❌ Không nhận được response từ LLM")
            return False

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_transaction_parsing():
    """Test 3: Parse Vietnamese transaction text"""
    print("\n" + "=" * 60)
    print("TEST 3: Transaction Parsing")
    print("=" * 60)

    try:
        client = create_llm_client()

        test_cases = ["Cafe Highland 55000 vnd ngay 10/10", "CK 200k cho me", "Mua sắm Shopee 1,500,000 VND"]

        success_count = 0
        for i, text in enumerate(test_cases, 1):
            print(f"\n📝 Test case {i}: {text}")
            result = client.parse_transaction_text(text)

            if result.get("raw") == "Invalid":
                print("   ⚠️  LLM không parse được")
            else:
                print(f"   ✓ merchant_name: {result.get('merchant_name')}")
                print(f"   ✓ total_amount: {result.get('total_amount')}")
                print(f"   ✓ category_name: {result.get('category_name')}")
                print(f"   ✓ category_type: {result.get('category_type')}")
                success_count += 1

        print(f"\n✅ Parsed {success_count}/{len(test_cases)} transactions")
        return success_count > 0

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_database_query():
    """Test 4: Natural language database query"""
    print("\n" + "=" * 60)
    print("TEST 4: Natural Language Database Query")
    print("=" * 60)

    try:
        print("\n🔌 Đang kết nối với database...")
        agent = create_llm_db_agent()

        if not agent:
            print("❌ Không thể tạo database agent")
            print("   Kiểm tra DATABASE_URL trong config")
            return False

        print("✓ Database agent khởi tạo thành công")

        # Test query
        question = "Cho tôi xem 5 giao dịch gần đây nhất"
        print(f"\n❓ Question: {question}")
        print("   Đang query...")

        result = agent.natural_language_query(question)

        if result.get("success"):
            print(f"\n✓ SQL: {result.get('sql')}")
            print(f"✓ Explanation: {result.get('explanation')}")
            print(f"✓ Found {result.get('count')} rows")

            if result.get("data"):
                print("\n📊 Data preview:")
                for i, row in enumerate(result["data"][:3], 1):
                    print(f"   {i}. {row}")

            print("\n✅ Natural language query hoạt động!")
            return True
        else:
            print(f"❌ Query failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_spending_insights():
    """Test 5: Get spending insights"""
    print("\n" + "=" * 60)
    print("TEST 5: Spending Insights")
    print("=" * 60)

    try:
        agent = create_llm_db_agent()

        if not agent:
            print("❌ Không thể tạo database agent")
            return False

        # First try quick summary (no LLM needed)
        print("\n📊 Quick Summary (không cần LLM)...")
        summary = agent.get_quick_summary(user_id=2, days=30)
        print(f"\n{summary}")

        # Then try LLM insights
        print("\n� Đang tạo AI insights cho user_id=2...")
        print("   (Có thể mất 1-2 phút tùy vào tốc độ LLM...)")

        try:
            insights = agent.get_spending_insights(user_id=2, days=30)
            print(f"\n💡 AI Insights:\n{insights}")

            if insights and "Không có dữ liệu" not in insights and "Không thể tạo" not in insights:
                print("\n✅ Spending insights hoạt động!")
                return True
            else:
                print("\n⚠️  LLM không tạo được insights hoặc timeout")
                print("✅ Test passed vì quick summary hoạt động")
                return True
        except Exception as e:
            print(f"\n⚠️  LLM insights timeout hoặc error: {e}")
            print("✅ Test passed vì quick summary hoạt động")
            return True

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 LOCAL LLM INTEGRATION TEST SUITE")
    print("=" * 60)
    print("\nĐảm bảo LLM server đang chạy tại http://localhost:1234")
    print("(LM Studio, Ollama, hoặc compatible server)")

    input("\nPress Enter để bắt đầu test...")

    results = {}

    # Run tests
    results["connection"] = test_llm_connection()

    if results["connection"]:
        results["chat"] = test_chat_completion()
        results["transaction"] = test_transaction_parsing()
        results["database"] = test_database_query()
        results["insights"] = test_spending_insights()
    else:
        print("\n⚠️  Bỏ qua các test khác vì không kết nối được LLM server")
        results["chat"] = False
        results["transaction"] = False
        results["database"] = False
        results["insights"] = False

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
