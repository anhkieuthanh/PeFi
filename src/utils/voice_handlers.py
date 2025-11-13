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
        # Add optimization parameters
        torch_dtype=torch.float16 if (torch is not None and torch.cuda.is_available()) else None,  # Use FP16 on GPU for 2x speed
    )
    return _transcriber


# Import helper functions (text parsing and DB) - guard for different run contexts
try:
    from .text_processor import parse_text_for_info
except Exception:
    # adjust sys.path and retry if running from repo root
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.utils.text_processor import parse_text_for_info

try:
    from database.db_operations import add_bill
except Exception:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from database.db_operations import add_bill

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

                # Parse and save transaction (both blocking) in threads
                payload = await asyncio.to_thread(parse_text_for_info, text_result)
                if payload == {"raw": "Invalid"}:
                    await context.bot.send_message(chat_id=chat_id, text="Văn bản không chứa thông tin giao dịch hợp lệ.")
                    return

                result = await asyncio.to_thread(add_bill, payload)
                
                elapsed_time = time.time() - process_start
                logger.info(f"✅ Voice processing completed in {elapsed_time:.2f}s")
                
                if result.get("success"):
                    transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
                    await context.bot.send_message(chat_id=chat_id, text=transaction_info)
                else:
                    error_msg = result.get("error", "Không thể lưu giao dịch")
                    logger.error("Lỗi khi lưu bill từ giọng nói: %s", error_msg)
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi khi lưu: {error_msg}")

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
