#!/usr/bin/env python3
"""
Quick test for Gemini API functionality
Tests text and vision models with sample inputs
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import logging  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_gemini_text():
    """Test Gemini text model with Vietnamese transaction"""
    print("\n" + "=" * 60)
    print("TEST: Gemini Text Model")
    print("=" * 60)

    try:
        from utils.text_processor import parse_text_for_info

        test_text = "Cafe Highland 55000 vnd ngay 10/10"
        print(f"\nInput: {test_text}")
        print("\nProcessing...")

        result = parse_text_for_info(test_text)

        print("\nResult:")
        if result.get("raw") == "Invalid":
            print("❌ Gemini returned Invalid")
            return False

        for key, value in result.items():
            print(f"  {key}: {value}")

        # Check required fields
        if result.get("total_amount") and result.get("category_name"):
            print("\n✅ Text processing successful!")
            return True
        else:
            print("\n⚠️  Missing required fields")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_gemini_vision():
    """Test Gemini vision model with sample prompt"""
    print("\n" + "=" * 60)
    print("TEST: Gemini Vision Model (Config Only)")
    print("=" * 60)

    try:
        import config
        from utils.promt import get_prompt_path, read_promt_file

        # Just test that we can load the model and prompt
        model = config.get_vision_model()
        prompt = read_promt_file(get_prompt_path("image_input.txt"))

        print(f"\n✓ Model loaded: {model.model_name}")
        print(f"✓ Prompt loaded: {len(prompt)} characters")
        print(f"✓ Prompt preview: {prompt[:150]}...")

        print("\n✅ Vision model configuration successful!")
        print("   (Actual image processing requires a real image URL)")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_config_only():
    """Test just the configuration"""
    print("\n" + "=" * 60)
    print("TEST: Configuration")
    print("=" * 60)

    try:
        import config

        print(f"\n✓ TOKEN: {'*' * 20}{config.TOKEN[-10:] if config.TOKEN else 'None'}")
        print(f"✓ GEMINI_API_KEY: {'*' * 30}{config.GEMINI_API_KEY[-10:] if config.GEMINI_API_KEY else 'None'}")
        print(f"✓ DATABASE_URL: {'SET' if config.DATABASE_URL else 'NOT SET'}")

        text_model = config.get_text_model()
        vision_model = config.get_vision_model()

        print(f"✓ Text model: {text_model.model_name}")
        print(f"✓ Vision model: {vision_model.model_name}")

        print("\n✅ Configuration successful!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🧪 Quick Gemini API Test\n")

    results = []

    # Test config first
    results.append(("Configuration", test_config_only()))

    # Test vision config
    results.append(("Vision Model Config", test_gemini_vision()))

    # Test text processing (makes actual API call)
    print("\n⚠️  The next test will make an actual Gemini API call")
    input("Press Enter to continue or Ctrl+C to skip...")
    results.append(("Text Processing", test_gemini_text()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")

    passed_count = sum(1 for _, p in results if p)
    total = len(results)

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed_count} test(s) failed")
        sys.exit(1)
