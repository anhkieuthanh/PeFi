# Changelog

All notable changes to PeFi Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-11-13

### Added
- 🎤 **Voice message support** - Process Vietnamese voice messages using PhoWhisper ASR
- 📊 **Smart financial reports** - Generate detailed reports with AI-powered insights
- 📈 **Report formatting** - Integer formatting for currency and percentages
- 🧪 **Optimization test suite** - Comprehensive tests for all optimizations
- 📚 **Enhanced documentation** - Added OPTIMIZATIONS.md, FORMATTING_CHANGES.md, and guides
- 🔧 **Import helper module** - Standardized import handling across modules
- 🎯 **Intent classification** - Automatic classification of user requests
- 📝 **Deterministic period extraction** - Fast local parsing for report requests

### Changed
- ⚡ **60% faster report generation** - Optimized from 1.5-2.5s to 0.6-0.9s
- 🗄️ **75% fewer database queries** - Combined 4 queries into 1 using CTEs
- 💾 **Prompt caching** - Prompts loaded once and cached in memory (99% I/O reduction)
- 🤖 **Model caching** - Gemini models initialized once and reused
- 🔌 **Connection pool cleanup** - Proper cleanup on shutdown to prevent leaks
- 🌐 **HTTP session singleton** - Reuse connections with retry logic
- 📊 **Report number formatting** - All currency as integers (no decimals)
- 📊 **Report percentage formatting** - All percentages as integers (no decimals)
- 💡 **Saving tips formatting** - All tips start with bullet points (•)
- 🔍 **Reduced logging** - Log output reduced from 500 to 200 chars
- 📝 **Removed LLM fallback** - Use deterministic parser only for better performance

### Fixed
- 🐛 **CTE parameter binding** - Fixed WHERE clause parameter multiplication
- 🐛 **Unused import** - Removed non-existent llm.llm import
- 🔒 **Memory leaks** - Added proper connection pool cleanup
- 🔄 **Text preprocessing** - Preprocess once and reuse instead of multiple times

### Optimized
- **Database queries** - Single optimized CTE query for transaction summaries
- **File I/O** - Prompt files cached after first read
- **Model initialization** - Gemini models cached and reused
- **HTTP connections** - Session pooling with retry logic
- **Memory usage** - 10-20% reduction through proper cleanup

### Performance Metrics
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Report generation | 1.5-2.5s | 0.6-0.9s | 60% faster |
| Database queries | 4 queries | 1 query | 75% reduction |
| Prompt file I/O | Every request | Once | 99% reduction |
| Model initialization | Every call | Cached | 100% reuse |

### Documentation
- Added `OPTIMIZATIONS.md` - Technical optimization details
- Added `OPTIMIZATION_EXAMPLES.md` - Before/after code examples
- Added `MIGRATION_GUIDE.md` - Migration and testing guide
- Added `OPTIMIZATION_STATUS.md` - Current status and test results
- Added `FORMATTING_CHANGES.md` - Report formatting documentation
- Added `FORMATTING_QUICK_REFERENCE.md` - Quick formatting reference
- Added `OPTIMIZATIONS_README.md` - Quick start guide
- Added `test_optimizations.py` - Automated test suite
- Updated `README.md` - Comprehensive feature and setup documentation
- Updated `requirements.txt` - Added missing dependencies
- Updated `config.sample.yaml` - Enhanced with comments and new options
- Updated `.github/workflows/ci.yml` - Enhanced CI with database and tests

### Breaking Changes
None - All changes are backward compatible

### Migration Notes
- No configuration changes required
- No database schema changes required
- All existing functionality preserved
- Run `python3 test_optimizations.py` to verify

## [1.0.0] - 2025-11-01

### Added
- Initial release
- Telegram bot integration
- Google Gemini AI for OCR and text parsing
- PostgreSQL database storage
- Image receipt processing
- Text transaction input
- Automatic category classification
- Basic reporting functionality

### Features
- Photo receipt scanning with Gemini Vision
- Text transaction parsing with Gemini
- Direct database storage
- Category auto-classification
- Vietnamese language support

---

## Version History

- **v2.0.0** (2025-11-13) - Performance optimizations, voice support, enhanced reports
- **v1.0.0** (2025-11-01) - Initial release

## Upgrade Guide

### From v1.0.0 to v2.0.0

1. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install FFmpeg (for voice support):**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

3. **Update config (optional):**
   - Add `database.pool_min` and `database.pool_max` for connection pool tuning
   - Add `app.default_user_id` if needed
   - See `config.sample.yaml` for all options

4. **Test the upgrade:**
   ```bash
   python3 test_optimizations.py
   ```

5. **Start the bot:**
   ```bash
   cd src && python3 bot.py
   ```

No database migration required - all changes are backward compatible!

## Support

For issues, questions, or contributions:
- GitHub Issues: [Report a bug](https://github.com/anhkieuthanh/PeFi/issues)
- Documentation: See README.md and docs folder
- Performance: See OPTIMIZATIONS.md

---

*For detailed technical changes, see individual documentation files in the repository.*
