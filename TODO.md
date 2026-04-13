# Fix Terminal Logging Issue (httpx verbose "OK\" malformation)

## Status: Step 1 Complete ✅

**Problem**: httpx INFO logs from Telegram polling show malformed \"OK\" output, cluttering terminal.

**Root Cause**: logging.INFO enables httpx verbose logs during getUpdates polling.

**Plan**:
- [x] Step 1: Suppress httpx logger to WARNING in config.py
- [ ] Step 2: Test by running `python main.py`
- [ ] Step 3: Verify clean terminal output
- [ ] Step 4: Complete if fixed

**Next**: Run `python main.py` to test. Expect clean logs without httpx spam.

**Expected Result**: Clean terminal with only app logs, no httpx spam.

