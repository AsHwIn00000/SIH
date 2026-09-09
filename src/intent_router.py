# src/intent_router.py
"""
HEXA Auto Model Router — selects the best available local model per turn.

Routing priority (first match wins):
  1. Image attachment present          → vision_ocr  → qwen3-vl:8b
  2. Prompt keywords: code / script    → coding      → qwen2.5-coder:latest
  3. Prompt keywords: math / reasoning → reasoning   → deepseek-r1:latest
  4. Prompt keywords: OCR / blueprint  → vision_ocr  → qwen3-vl:8b
  5. No match                          → general     → qwen3.5:9b (fallback chain)

If the preferred model is not installed, falls back gracefully to the
session's current model. The user's configured default is never permanently
changed — routing only applies for the current turn.
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("hexa.intent_router")

# ── Model Registry ────────────────────────────────────────────────────────────
# Maps category → preferred Ollama model handle.
# Listed in order of preference — the router tries the first installed one.
MODEL_REGISTRY: Dict[str, list[str]] = {
    "coding":         ["qwen2.5-coder:latest", "qwen2.5-coder:7b", "qwen2.5-coder:3b", "qwen3:4b"],
    "reasoning_math": ["deepseek-r1:latest", "deepseek-r1:7b", "qwen3.5:9b", "qwen3:4b"],
    "vision_ocr":     ["qwen3-vl:8b", "qwen2-vl:latest", "llava:latest", "moondream:latest"],
    "general_chat":   ["qwen3.5:9b", "qwen3:4b", "qwen2.5:latest"],
}

# ── Keyword Patterns ──────────────────────────────────────────────────────────
_CODING = re.compile(
    r"\b(python|def |class |function|script|c\+\+|cpp|java|javascript|"
    r"bash|shell|git|sql|compile|debug|refactor|error|traceback|"
    r"algorithm|code|program|implement|fix the bug|syntax)\b",
    re.IGNORECASE,
)

_MATH_REASONING = re.compile(
    r"\b(calculate|equation|math|formula|stress|tolerance|financial|"
    r"audit|margin|pressure|flow rate|derivative|step.?by.?step|"
    r"reasoning|derive|proof|compute|integral|differentiate|"
    r"percentage|budget|forecast|estimate)\b",
    re.IGNORECASE,
)

_VISION_OCR = re.compile(
    r"\b(scanned|ocr|drawing|blueprint|p&id|schematic|handwritten|"
    r"photograph|diagram|visual|figure|chart|table.*image|read.*image|"
    r"extract.*text|what.*image|describe.*image|analyse.*image|"
    r"analyze.*image|what is in|what does.*show)\b",
    re.IGNORECASE,
)

# ── Public API ────────────────────────────────────────────────────────────────

def register_model(task_category: str, model_handle: str) -> None:
    """Add or replace a model for a task category at runtime."""
    if task_category in MODEL_REGISTRY:
        if model_handle not in MODEL_REGISTRY[task_category]:
            MODEL_REGISTRY[task_category].insert(0, model_handle)
    else:
        MODEL_REGISTRY[task_category] = [model_handle]
    logger.info("Registered model '%s' for category '%s'", model_handle, task_category)


def classify_task_intent(
    prompt: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Classify prompt + attachments into a routing category.

    Returns one of: 'vision_ocr', 'coding', 'reasoning_math', 'general_chat'
    """
    attachments = attachments or []

    # Image attachment → always vision
    for att in attachments:
        name = str(att.get("name") or att.get("filename") or "").lower()
        mime = str(att.get("mime") or att.get("type") or "").lower()
        if mime.startswith("image/") or any(
            name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".gif")
        ):
            return "vision_ocr"

    # Keyword match — order matters, more specific first
    if _VISION_OCR.search(prompt):
        return "vision_ocr"
    if _CODING.search(prompt):
        return "coding"
    if _MATH_REASONING.search(prompt):
        return "reasoning_math"

    return "general_chat"


def route_model(
    prompt: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Select the best model for this turn.

    If preferred_model is explicitly set (user picked a model in the UI),
    that choice is respected — auto-routing is skipped.

    Returns dict with keys: selected_model, category, auto_selected
    """
    if preferred_model and preferred_model.strip():
        return {
            "selected_model": preferred_model.strip(),
            "category": "user_override",
            "auto_selected": False,
        }

    category = classify_task_intent(prompt, attachments)

    # Return the full preference list — the caller (chat_routes.py) will
    # pick the first one that's actually installed in Ollama.
    candidates = MODEL_REGISTRY.get(category, MODEL_REGISTRY["general_chat"])
    selected_model = candidates[0] if candidates else ""

    logger.info(
        "[intent-router] category=%s → preferred=%s (candidates=%s)",
        category, selected_model, candidates[:3],
    )

    return {
        "selected_model": selected_model,
        "category": category,
        "auto_selected": True,
        "candidates": candidates,
    }
