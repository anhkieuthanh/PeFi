#!/usr/bin/env python3
"""
Demo: Sử dụng Local LLM với database

Ví dụ về cách tích hợp local LLM vào workflow
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm.llm import create_llm_client, create_llm_db_agent  # noqa: E402


def demo_1_parse_transaction():
    """Demo 1: Parse transaction text"""
    print("\n" + "=" * 60)
    print("DEMO 1: Parse Transaction với Local LLM")
    print("=" * 60)

    client = create_llm_client()

    transactions = [
        "Cafe Highlands 55k hôm qua",
        "Đổ xăng 200 nghìn",
        "Nhận lương 15 triệu từ công ty",
        "Mua điện thoại 8,500,000 vnđ",
    ]

    for text in transactions:
        print(f"\n📝 Input: {text}")
        result = client.parse_transaction_text(text)

        if result.get("raw") != "Invalid":
            print(f"   → Merchant: {result.get('merchant_name')}")
            print(f"   → Amount: {result.get('total_amount'):,} VND")
            print(
                f"   → Category: {result.get('category_name')} ({'Thu nhập' if result.get('category_type') == 1 else 'Chi tiêu'})"
            )
            print(f"   → Date: {result.get('bill_date')}")
        else:
            print("   → ❌ Không parse được")


def demo_2_natural_language_query():
    """Demo 2: Query database bằng natural language"""
    print("\n" + "=" * 60)
    print("DEMO 2: Natural Language Database Query")
    print("=" * 60)

    agent = create_llm_db_agent()

    if not agent:
        print("❌ Không kết nối được database")
        return

    questions = [
        "Cho tôi xem tổng chi tiêu theo từng category",
        "Tìm 3 giao dịch có giá trị cao nhất",
        "Đếm số giao dịch của mỗi user",
        "Cho tôi xem chi tiêu ăn uống trong tháng này",
    ]

    for question in questions:
        print(f"\n❓ {question}")
        result = agent.natural_language_query(question)

        if result.get("success"):
            print(f"   SQL: {result['sql']}")
            print(f"   → Found {result['count']} records")

            # Show first 3 results
            for i, row in enumerate(result["data"][:3], 1):
                print(f"   {i}. {row}")
        else:
            print(f"   ❌ {result.get('error')}")


def demo_3_insights():
    """Demo 3: Get financial insights"""
    print("\n" + "=" * 60)
    print("DEMO 3: Financial Insights với Local LLM")
    print("=" * 60)

    agent = create_llm_db_agent()

    if not agent:
        print("❌ Không kết nối được database")
        return

    print("\n📊 Phân tích chi tiêu 30 ngày qua...")
    insights = agent.get_spending_insights(user_id=2, days=30)

    print(f"\n💡 Insights:\n{insights}")


def demo_4_interactive_chat():
    """Demo 4: Interactive chat về database"""
    print("\n" + "=" * 60)
    print("DEMO 4: Interactive Database Chat")
    print("=" * 60)
    print("Type 'exit' để thoát\n")

    agent = create_llm_db_agent()

    if not agent:
        print("❌ Không kết nối được database")
        return

    while True:
        try:
            question = input("\n❓ Hỏi về dữ liệu: ").strip()

            if question.lower() in ["exit", "quit", "q"]:
                print("👋 Bye!")
                break

            if not question:
                continue

            print("   Đang query...")
            result = agent.natural_language_query(question)

            if result.get("success"):
                print(f"\n   SQL: {result['sql']}")
                print(f"   Found: {result['count']} records\n")

                # Pretty print results
                for i, row in enumerate(result["data"][:10], 1):
                    print(f"   {i}. {row}")

                if result["count"] > 10:
                    print(f"   ... và {result['count'] - 10} records nữa")
            else:
                print(f"\n   ❌ {result.get('error')}")

        except KeyboardInterrupt:
            print("\n👋 Bye!")
            break
        except Exception as e:
            print(f"\n   ❌ Lỗi: {e}")


if __name__ == "__main__":
    print("\n🤖 LOCAL LLM + DATABASE DEMOS")
    print("=" * 60)
    print("Chọn demo:")
    print("1. Parse Transaction Text")
    print("2. Natural Language Query")
    print("3. Financial Insights")
    print("4. Interactive Chat")
    print("5. Run All")

    choice = input("\nNhập số (1-5): ").strip()

    if choice == "1":
        demo_1_parse_transaction()
    elif choice == "2":
        demo_2_natural_language_query()
    elif choice == "3":
        demo_3_insights()
    elif choice == "4":
        demo_4_interactive_chat()
    elif choice == "5":
        demo_1_parse_transaction()
        demo_2_natural_language_query()
        demo_3_insights()
    else:
        print("❌ Invalid choice")
