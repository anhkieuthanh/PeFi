# Hàm tải về audio gửi từ telegram
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes
from src.utils.http_session import get_session

logger = logging.getLogger(__name__)

# Lazy-loaded ASR pipeline - Use smaller/faster model by default for better performance
# Options: vinai/PhoWhisper-small (fastest), vinai/PhoWhisper-medium, vinai/PhoWhisper-large (slowest)
_PHOWHISPER_MODEL = os.environ.get("PHOWHISPER_MODEL", "vinai/PhoWhisper-small")
_transcriber = None


def get_transcriber():
    """Return a cached transformers pipeline for ASR (PhoWhisper-small by default for speed).

    Detects CUDA and uses GPU if available, otherwise CPU. Loading is lazy to
    avoid long startup time at import.
    """
    global _transcriber
    if _transcriber is not None:
        return _transcriber

    # Import heavy libs lazily to avoid import-time side effects
    try:
        import torch
    except Exception:
        torch = None

    try:
        from transformers import pipeline
    except Exception:
        pipeline = None

    # device: 0 for first GPU, -1 for CPU (transformers pipeline accepts int)
    device = 0 if (torch is not None and torch.cuda.is_available()) else -1

    if pipeline is None:
        raise RuntimeError("transformers.pipeline is not available; please install transformers")

    # create the pipeline with optimizations
    _transcriber = pipeline(
        "automatic-speech-recognition",
        model=_PHOWHISPER_MODEL,
        chunk_length_s=30,
        device=device,
        ignore_warning = True,
        # Add optimization parameters
        torch_dtype=torch.float16 if (torch is not None and torch.cuda.is_available()) else None,  # Use FP16 on GPU for 2x speed
    )
    return _transcriber


# Import helper functions (text parsing and DB) - guard for different run contexts
try:
    from .text_processor import parse_text_for_info, generate_user_response, extract_period_and_type, preprocess_text
except Exception:
    # adjust sys.path and retry if running from repo root
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.utils.text_processor import parse_text_for_info, generate_user_response, extract_period_and_type, preprocess_text

try:
    from database.db_operations import add_bill
except Exception:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from database.db_operations import add_bill

# Import reporting module for voice-based reports
try:
    from src.reporting.reporting import get_summary, generate_report
except Exception:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.reporting.reporting import get_summary, generate_report

# Load upload dir from config when possible
try:
    import config

    UPLOAD_DIR = getattr(config, "UPLOAD_DIR", "uploads")
except Exception:
    # fallback to repo-level uploads
    repo_root = Path(__file__).resolve().parents[2]
    UPLOAD_DIR = str(repo_root / "uploads")

Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Xử lý tin nhắn giọng nói: tải về, chuyển đổi, trích xuất văn bản, lưu vào DB và trả lời.
    """
    if not update.message or not update.message.voice:
        return

    voice = update.message.voice
    chat_id = update.message.chat_id

    dest_path = None
    dest_wav = None
    try:
        # Tải tệp giọng nói về
        voice_file = await voice.get_file()
        file_url = getattr(voice_file, "file_path", None)
        if not file_url:
            await context.bot.send_message(chat_id=chat_id, text="Không thể xử lí giọng nói. Vui lòng thử lại.")
            return

        # Determine extension from URL or default to .ogg
        ext = Path(file_url).suffix or ".ogg"
        timestamp = int(time.time())
        filename = f"voice_{chat_id}_{timestamp}{ext}"
        dest_path = Path(UPLOAD_DIR) / filename

        # Try library download methods first, then fallback to HTTP GET
        downloaded = False
        try:
            if hasattr(voice_file, "download_to_drive"):
                # async method in newer python-telegram-bot
                await voice_file.download_to_drive(custom_path=str(dest_path))
                downloaded = True
            elif hasattr(voice_file, "download"):
                # some versions expose download(out=...)
                # try await first, then sync
                try:
                    await voice_file.download(out=str(dest_path))
                except TypeError:
                    voice_file.download(out=str(dest_path))
                downloaded = True
        except Exception:
            logger.exception("Library download failed, will try HTTP fallback")

        if not downloaded:
            # Fallback: fetch URL directly using shared requests Session
            try:
                session = get_session()
                timeout = getattr(config, "HTTP_TIMEOUT", 30)
                r = session.get(file_url, timeout=timeout)
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    f.write(r.content)
                downloaded = True
            except Exception:
                logger.exception("Failed to download voice file via HTTP fallback")

        if not downloaded:
            await context.bot.send_message(chat_id=chat_id, text="❌ Không thể xử lí âm thanh. Vui lòng thử lại.")
            return

        # Convert OGG/OPUS/OGA -> WAV suitable for Whisper and transcribe
        ext_lower = dest_path.suffix.lower()
        audio_for_stt = dest_path
        if ext_lower in (".oga", ".ogg", ".opus"):
            dest_wav = dest_path.with_suffix(".wav")
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logger.error("ffmpeg not found; cannot convert audio for STT")
                return
            # Optimized ffmpeg command for faster conversion
            cmd = [
                ffmpeg_path,
                "-y",  # Overwrite output
                "-i", str(dest_path),
                "-ar", "16000",  # Sample rate for Whisper
                "-ac", "1",  # Mono
                "-sample_fmt", "s16",  # 16-bit PCM
                "-loglevel", "error",  # Reduce ffmpeg output
                "-threads", "2",  # Use 2 threads for faster conversion
                str(dest_wav),
            ]
            try:
                await asyncio.to_thread(subprocess.run, cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                audio_for_stt = dest_wav
                logger.info("Audio converted to WAV for STT")
            except Exception:
                logger.exception("ffmpeg conversion failed")
                return

        # Offload transcription + parsing + DB save to a background task so the bot
        # can reply quickly. The heavy work runs in threads via asyncio.to_thread.
        await context.bot.send_message(chat_id=chat_id, text="🔊 Đã nhận file — đang xử lí ở background. Bạn sẽ nhận thông báo khi hoàn tất.")

        async def _process_and_respond(audio_path: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
            import time
            process_start = time.time()
            
            try:
                # Load transcriber (may be heavy) in a thread
                stt = await asyncio.to_thread(get_transcriber)

                # Run ASR in thread
                out = await asyncio.to_thread(stt, str(audio_path))

                # Extract text from pipeline output (be robust to dict/list/string returns)
                text_result = ""
                if isinstance(out, dict):
                    text_result = out.get("text", "")
                elif isinstance(out, list):
                    parts = []
                    for o in out:
                        if isinstance(o, dict):
                            parts.append(o.get("text", ""))
                        else:
                            parts.append(str(o))
                    text_result = " ".join([p for p in parts if p])
                else:
                    text_result = str(out)

                if not text_result:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Xử lí không thành công. Vui lòng thử lại.")
                    return

                logger.info(f"Voice transcribed: {text_result}")
                
                # Check if transcription is too short or unclear
                if len(text_result.strip()) < 5:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="🤔 Tôi không nghe rõ. Bạn có thể nói lại được không?\n\nGợi ý:\n• Nói rõ ràng hơn\n• Ghi âm ở nơi yên tĩnh\n• Hoặc gõ text thay vì voice"
                    )
                    return
                
                # Classify intent using scoring system for better accuracy
                norm = preprocess_text(text_result).lower()
                
                # Score-based classification
                transaction_score = 0
                report_score = 0
                
                # Transaction indicators (stronger signals)
                transaction_keywords = [
                    ("mua", 3), ("chi", 3), ("trả", 3), ("thanh toán", 3),
                    ("chuyển khoản", 3), ("ck", 2), ("nạp", 2), ("rút", 2),
                    ("gửi", 2), ("bán", 2), ("thu", 2), ("nhận", 2)
                ]
                for keyword, weight in transaction_keywords:
                    if keyword in norm:
                        transaction_score += weight
                
                # Check for amount (strong transaction signal)
                import re
                has_number = bool(re.search(r'\d+', norm))
                has_currency = any(unit in norm for unit in ["nghìn", "triệu", "k", "đồng", "vnd"])
                if has_number:
                    transaction_score += 4
                if has_currency:
                    transaction_score += 2
                
                # Report indicators (stronger signals)
                report_keywords = [
                    ("tổng chi", 5), ("tổng thu", 5), ("tổng hợp", 5),
                    ("báo cáo", 4), ("xem chi tiêu", 4), ("xem thu nhập", 4),
                    ("thống kê", 3), ("tổng kết", 3), ("chi tiết", 2),
                    ("tháng này", 2), ("tháng trước", 2), ("hôm nay", 1),
                    ("tuần này", 2), ("năm nay", 2)
                ]
                for keyword, weight in report_keywords:
                    if keyword in norm:
                        report_score += weight
                
                # Penalty: if has report keywords, reduce transaction score
                if report_score > 0:
                    transaction_score = max(0, transaction_score - 2)
                
                # Penalty: if has transaction keywords, reduce report score slightly
                if transaction_score > 0:
                    report_score = max(0, report_score - 1)
                
                # Determine intent based on scores
                TRANSACTION_THRESHOLD = 5
                REPORT_THRESHOLD = 4
                
                is_transaction = transaction_score >= TRANSACTION_THRESHOLD
                is_report_request = report_score >= REPORT_THRESHOLD
                
                logger.info(f"Intent scores - Transaction: {transaction_score}, Report: {report_score}")
                
                # Handle dual intent (both transaction and report)
                if is_report_request and is_transaction:
                    logger.info("Voice classified as: BOTH transaction and report")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="📝 Tôi nghe thấy cả giao dịch VÀ yêu cầu báo cáo. Tôi sẽ xử lý cả hai nhé!"
                    )
                    
                    # Process transaction first
                    try:
                        payload = await asyncio.to_thread(parse_text_for_info, text_result)
                        if payload != {"raw": "Invalid"}:
                            result = await asyncio.to_thread(add_bill, payload)
                            if result.get("success"):
                                transaction_info = result.get("transaction_info", "Đã lưu giao dịch")
                                await context.bot.send_message(chat_id=chat_id, text=f"✅ Giao dịch:\n{transaction_info}")
                            else:
                                await context.bot.send_message(chat_id=chat_id, text="⚠️ Không thể lưu giao dịch, nhưng tôi sẽ tạo báo cáo.")
                    except Exception as e:
                        logger.exception("Error processing transaction in dual intent")
                        await context.bot.send_message(chat_id=chat_id, text="⚠️ Lỗi khi lưu giao dịch, nhưng tôi sẽ tạo báo cáo.")
                    
                    # Then process report (code continues below)
                    # Fall through to report processing
                
                # Process based on intent
                if is_report_request:
                    # Handle report request
                    logger.info("Voice classified as: Report request")
                    
                    try:
                        import config as _cfg
                        user_id = getattr(_cfg, "DEFAULT_USER_ID", 2)
                    except Exception:
                        user_id = 2
                    
                    # Extract period from voice text
                    report_req = extract_period_and_type(text_result)
                    if not report_req:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="Không thể hiểu yêu cầu báo cáo. Vui lòng nói rõ hơn, ví dụ:\n• 'Tổng hợp tháng này'\n• 'Báo cáo chi tiêu tháng 11'\n• 'Xem tổng thu tháng trước'"
                        )
                        return
                    
                    # Get data from database
                    start = report_req.get("start_date")
                    end = report_req.get("end_date")
                    typ = report_req.get("type", "both")
                    
                    summary = await asyncio.to_thread(get_summary, user_id, start, end, typ)
                    if not summary or summary.get("error"):
                        err_text = "Lỗi khi truy vấn dữ liệu"
                        if isinstance(summary, dict) and summary.get("error"):
                            err_text = str(summary.get("error"))
                        await context.bot.send_message(chat_id=chat_id, text=err_text)
                        return
                    
                    # Generate report
                    period_text = report_req.get("raw_period_text") or f"{start} đến {end}"
                    report_resp = await asyncio.to_thread(generate_report, summary, period_text, typ, start, end)
                    
                    elapsed_time = time.time() - process_start
                    logger.info(f"✅ Voice report generation completed in {elapsed_time:.2f}s")
                    
                    if isinstance(report_resp, dict):
                        text = str(report_resp.get("text") or "")
                        try:
                            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                        except Exception:
                            await context.bot.send_message(chat_id=chat_id, text=text)
                    else:
                        await context.bot.send_message(chat_id=chat_id, text=str(report_resp))
                
                elif is_transaction:
                    # Handle transaction recording only
                    logger.info("Voice classified as: Transaction recording")
                    
                    payload = await asyncio.to_thread(parse_text_for_info, text_result)
                    if payload == {"raw": "Invalid"}:
                        # Ask user to clarify
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="🤔 Tôi không hiểu rõ giao dịch này. Bạn có thể:\n\n1️⃣ Nói lại rõ hơn (ví dụ: 'Mua cafe năm mươi nghìn')\n2️⃣ Hoặc gõ text: 'Cafe 50k'"
                        )
                        return

                    result = await asyncio.to_thread(add_bill, payload)
                    
                    elapsed_time = time.time() - process_start
                    logger.info(f"✅ Voice transaction processing completed in {elapsed_time:.2f}s")
                    
                    if result.get("success"):
                        transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
                        await context.bot.send_message(chat_id=chat_id, text=transaction_info)
                    else:
                        error_msg = result.get("error", "Không thể lưu giao dịch")
                        logger.error("Lỗi khi lưu bill từ giọng nói: %s", error_msg)
                        await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi khi lưu: {error_msg}")
                
                else:
                    # Unclear intent - ask user
                    logger.info("Voice classified as: Unclear intent")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="🤔 Tôi không chắc bạn muốn làm gì. Bạn muốn:\n\n1️⃣ Ghi nhận giao dịch? (Nói: 'Mua cafe 50k')\n2️⃣ Xem báo cáo? (Nói: 'Tổng hợp tháng này')\n\nHoặc gõ text cho chính xác hơn!"
                    )

            except Exception:
                elapsed_time = time.time() - process_start
                logger.error(f"❌ Voice processing failed after {elapsed_time:.2f}s")
                logger.exception("Error during background STT or DB save")
                try:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Lỗi khi xử lý giọng nói. Vui lòng thử lại sau.")
                except Exception:
                    logger.exception("Failed to send error message to user after background failure")
            finally:
                # Best-effort: delete the audio file after background processing completes
                try:
                    ap = Path(audio_path)
                    if ap.exists() and str(ap.resolve()).startswith(str(Path(UPLOAD_DIR).resolve())):
                        ap.unlink()
                        logger.info("Deleted background-processed audio file: %s", ap)
                except Exception:
                    logger.exception("Failed to delete background audio file: %s", audio_path)

        # Schedule background processing and return immediately
        background_task_created = False
        try:
            # Ensure we pass a string path into the background task
            task = asyncio.create_task(_process_and_respond(str(audio_for_stt), chat_id, context))
            background_task_created = True
        except Exception:
            logger.exception("Failed to schedule background voice processing")
    except Exception as e:
        logger.exception("Lỗi trong voice_handler")
        # Safely reference chat_id
        cid = getattr(update.message, "chat_id", None)
        if cid is not None:
            await context.bot.send_message(chat_id=cid, text=f"Đã có lỗi xảy ra: {e}")
    finally:
        # Best-effort cleanup of downloaded/converted files. Only remove files under UPLOAD_DIR.
        try:
            # If we scheduled a background task, let it handle file deletion after processing.
            if not background_task_created:
                if dest_path is not None:
                    try:
                        dp = Path(dest_path)
                        if dp.exists() and str(dp.resolve()).startswith(str(Path(UPLOAD_DIR).resolve())):
                            dp.unlink()
                            logger.info("Deleted downloaded voice file: %s", dp)
                    except Exception:
                        logger.exception("Failed to delete downloaded voice file: %s", dest_path)

                if dest_wav is not None:
                    try:
                        dv = Path(dest_wav)
                        if dv.exists() and str(dv.resolve()).startswith(str(Path(UPLOAD_DIR).resolve())):
                            dv.unlink()
                            logger.info("Deleted converted wav: %s", dv)
                    except Exception:
                        logger.exception("Failed to delete converted wav: %s", dest_wav)
        except Exception:
            logger.exception("Unexpected error during audio cleanup")
