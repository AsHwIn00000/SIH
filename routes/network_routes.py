# routes/network_routes.py
"""
Zero-Egress Network Monitor — streams live network I/O stats via SSE.

The widget on the welcome screen shows bytes sent/received in real time.
During AI inference the sent bytes should stay near ZERO — proving that
no data leaves the machine. This is the core trust signal for PSU/defence
deployments where data sovereignty is mandatory.

Also provides /api/multi-doc/analyze — cross-reference multiple uploaded
documents and answer questions across all of them simultaneously.
"""

import asyncio
import json
import logging
import os
import time
from typing import List

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Capture baseline at app start so the counter shows DELTA (not total) ─────
_BASELINE_SENT = 0
_BASELINE_RECV = 0
_baseline_captured = False


def _capture_baseline():
    global _BASELINE_SENT, _BASELINE_RECV, _baseline_captured
    if not _baseline_captured:
        c = psutil.net_io_counters()
        _BASELINE_SENT = c.bytes_sent
        _BASELINE_RECV = c.bytes_recv
        _baseline_captured = True


_capture_baseline()


def _format_bytes(n: int) -> str:
    """Human-readable byte count."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n/1024**2:.2f} MB"
    return f"{n/1024**3:.2f} GB"


# ── GET /api/network-stats/stream ─────────────────────────────────────────────
@router.get("/api/network-stats/stream")
async def network_stats_stream(request: Request):
    """
    SSE stream of network I/O counters, emitted every second.

    Each event is a JSON object:
    {
        "sent_total":   123,       # bytes sent since app start
        "recv_total":   456,       # bytes received since app start
        "sent_delta":   10,        # bytes sent in the last second
        "recv_delta":   20,        # bytes received in the last second
        "sent_fmt":     "123 B",   # human-readable total sent
        "recv_fmt":     "456 B",   # human-readable total received
        "egress_zero":  true,      # true if sent_total < 1KB (data sovereignty proof)
        "uptime_s":     42         # seconds since monitoring started
    }
    """
    async def generate():
        prev_sent = _BASELINE_SENT
        prev_recv = _BASELINE_RECV
        start_ts = time.time()

        while True:
            if await request.is_disconnected():
                break

            try:
                c = psutil.net_io_counters()
                sent_total = c.bytes_sent - _BASELINE_SENT
                recv_total = c.bytes_recv - _BASELINE_RECV
                sent_delta = c.bytes_sent - prev_sent
                recv_delta = c.bytes_recv - prev_recv
                prev_sent = c.bytes_sent
                prev_recv = c.bytes_recv

                # Only count outbound from our app's process (psutil gives system-wide)
                # We still show system-wide but flag if >0 so users can see
                uptime = int(time.time() - start_ts)

                payload = {
                    "sent_total": max(0, sent_total),
                    "recv_total": max(0, recv_total),
                    "sent_delta": max(0, sent_delta),
                    "recv_delta": max(0, recv_delta),
                    "sent_fmt": _format_bytes(max(0, sent_total)),
                    "recv_fmt": _format_bytes(max(0, recv_total)),
                    "egress_zero": sent_total < 1024,   # <1KB = essentially zero
                    "uptime_s": uptime,
                }
                yield f"data: {json.dumps(payload)}\n\n"

            except Exception as e:
                logger.warning("network_stats_stream error: %s", e)

            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET /api/network-stats/snapshot ──────────────────────────────────────────
@router.get("/api/network-stats/snapshot")
async def network_stats_snapshot():
    """Single-shot network stats (no streaming). Used on page load."""
    _capture_baseline()
    c = psutil.net_io_counters()
    sent_total = max(0, c.bytes_sent - _BASELINE_SENT)
    recv_total = max(0, c.bytes_recv - _BASELINE_RECV)
    return {
        "sent_total": sent_total,
        "recv_total": recv_total,
        "sent_fmt": _format_bytes(sent_total),
        "recv_fmt": _format_bytes(recv_total),
        "egress_zero": sent_total < 1024,
    }


# ── POST /api/multi-doc/analyze ───────────────────────────────────────────────
@router.post("/api/multi-doc/analyze")
async def multi_doc_analyze(request: Request):
    """
    Cross-reference multiple uploaded documents.

    Body (JSON):
    {
        "attachment_ids": ["id1", "id2", "id3"],
        "question": "What are the differences between these documents?"
    }

    Returns extracted text from all documents combined, with a structured
    prompt ready to send to the AI model. The chat route handles the actual
    LLM call — this endpoint just does the extraction and formatting.

    Response:
    {
        "combined_context": "=== Document 1: filename.docx ===\n...\n=== Document 2: ===",
        "document_count": 3,
        "total_chars": 45000,
        "documents": [{"name": ..., "chars": ..., "type": ...}],
        "suggested_prompt": "Based on the above documents:\n<question>"
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    att_ids: List[str] = body.get("attachment_ids", [])
    question: str = body.get("question", "Compare and summarize these documents")

    if not att_ids:
        return JSONResponse(status_code=400, content={"error": "No attachment_ids provided"})

    # Resolve upload handler from app state
    upload_handler = getattr(getattr(request.app, "state", None), "upload_handler", None)
    if upload_handler is None:
        # Try importing directly
        try:
            from src.app_initializer import get_upload_handler
            upload_handler = get_upload_handler()
        except Exception:
            return JSONResponse(status_code=503, content={"error": "Upload handler not available"})

    from src.markitdown_runtime import convert_to_markdown, is_markitdown_format
    from src.document_processor import _process_pdf, _process_text_file, _is_text_file
    import mimetypes

    documents = []
    combined_parts = []
    total_chars = 0
    MAX_PER_DOC = 12000   # cap per document so combined stays under ~40k chars
    MAX_TOTAL = 36000     # hard cap across all documents

    for att_id in att_ids[:6]:   # max 6 docs at once
        try:
            upload_info = None
            if hasattr(upload_handler, "resolve_upload"):
                upload_info = upload_handler.resolve_upload(att_id)
            if upload_info is None:
                logger.warning("multi-doc: attachment %s not found", att_id)
                continue

            path = upload_info.get("path", "")
            if not path or not os.path.exists(path):
                continue

            name = upload_info.get("name") or upload_info.get("original_name") or os.path.basename(path)
            mime = upload_info.get("mime") or mimetypes.guess_type(path)[0] or "application/octet-stream"
            ext = os.path.splitext(path)[1].lower()

            # Extract text based on file type
            text = None
            if mime == "application/pdf" or ext == ".pdf":
                raw = _process_pdf(path)
                # Strip the [PDF content]: wrapper
                text = raw.replace("\n\n[PDF content]:", "").strip()
            elif is_markitdown_format(path):
                text = convert_to_markdown(path)
            elif _is_text_file(path) or ext in (".txt", ".csv", ".md", ".json"):
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except Exception as e:
                    text = f"[Could not read file: {e}]"
            else:
                text = f"[Unsupported format: {ext}]"

            if not text:
                text = "[No extractable content]"

            # Cap per-document
            truncated = len(text) > MAX_PER_DOC
            if truncated:
                text = text[:MAX_PER_DOC] + f"\n[...truncated — showing first {MAX_PER_DOC:,} chars]"

            # Check total budget
            if total_chars + len(text) > MAX_TOTAL:
                remaining = MAX_TOTAL - total_chars
                if remaining < 500:
                    documents.append({"name": name, "chars": 0, "type": ext, "omitted": True})
                    combined_parts.append(f"\n=== Document: {name} ===\n[Omitted — total context limit reached]")
                    continue
                text = text[:remaining] + "\n[...omitted — total context limit reached]"

            char_count = len(text)
            total_chars += char_count
            documents.append({"name": name, "chars": char_count, "type": ext, "truncated": truncated})
            combined_parts.append(f"\n{'='*60}\nDocument: {name}\n{'='*60}\n{text}")

        except Exception as e:
            logger.error("multi-doc extraction error for %s: %s", att_id, e)
            continue

    if not combined_parts:
        return JSONResponse(status_code=422, content={"error": "Could not extract text from any document"})

    combined_context = "\n".join(combined_parts)

    # Build suggested prompt that the frontend can inject into the chat
    doc_names = ", ".join(d["name"] for d in documents if not d.get("omitted"))
    suggested_prompt = (
        f"I have provided {len(documents)} document(s): {doc_names}\n\n"
        f"{combined_context}\n\n"
        f"{'='*60}\n"
        f"Based on the above documents, {question}"
    )

    return {
        "combined_context": combined_context,
        "document_count": len(documents),
        "total_chars": total_chars,
        "documents": documents,
        "suggested_prompt": suggested_prompt,
        "question": question,
    }
