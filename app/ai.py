import time
import json
import httpx
from typing import Dict, Any
from app.config import settings

VALID_INTENTS = {"booking_request", "complaint", "status_query", "other"}

async def classify_and_draft_reply(masked_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifies intent and drafts an operations reply based strictly on masked data.
    Logs model, latency_ms, and token count.
    """
    start_time = time.perf_counter()

    prompt = f"""You are a field operations assistant.
Analyze this inbound event (all PII has been replaced with deterministic tokens):
{json.dumps(masked_payload, indent=2)}

Task:
1. Classify the customer or crew intent strictly into one of:
   - booking_request
   - complaint
   - status_query
   - other
2. Draft a professional 1-2 sentence suggested response for an operations dispatcher to review.

Respond with strictly valid JSON matching this schema:
{{
  "intent": "<one_of_the_four>",
  "suggested_reply": "<short_reply>"
}}
"""

    provider = settings.AI_PROVIDER.lower()

    # 1. Gemini Provider
    if provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1
                }
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=body)
                res.raise_for_status()
                data = res.json()
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)

                intent = parsed.get("intent", "other").lower()
                if intent not in VALID_INTENTS:
                    intent = "other"

                return {
                    "intent": intent,
                    "suggested_reply": parsed.get("suggested_reply", ""),
                    "model": "gemini-2.5-flash",
                    "latency_ms": round(latency_ms, 2),
                    "tokens_used": tokens
                }
        except Exception as exc:
            # Degrade gracefully to local heuristic
            pass

    # 2. Groq Provider
    if provider == "groq" and settings.GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            body = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a field operations assistant. Output only JSON."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=body, headers=headers)
                res.raise_for_status()
                data = res.json()
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                content = json.loads(data["choices"][0]["message"]["content"])
                tokens = data.get("usage", {}).get("total_tokens", 0)

                intent = content.get("intent", "other").lower()
                if intent not in VALID_INTENTS:
                    intent = "other"

                return {
                    "intent": intent,
                    "suggested_reply": content.get("suggested_reply", ""),
                    "model": "llama-3.3-70b-versatile",
                    "latency_ms": round(latency_ms, 2),
                    "tokens_used": tokens
                }
        except Exception:
            pass

    # 3. Deterministic Local Mock Provider (Zero-Cost / Unit Testing default)
    latency_ms = (time.perf_counter() - start_time) * 1000
    payload_str = json.dumps(masked_payload).lower()

    if any(k in payload_str for k in ["book", "schedule", "appointment", "reserve"]):
        intent = "booking_request"
        reply = "Thank you for reaching out. We have received your booking request and will confirm crew assignment shortly."
    elif any(k in payload_str for k in ["broken", "leak", "complain", "delay", "damaged", "fail"]):
        intent = "complaint"
        reply = "We apologize for the inconvenience. Our operations supervisor has been notified and is prioritizing this incident."
    elif any(k in payload_str for k in ["status", "where", "update", "when"]):
        intent = "status_query"
        reply = "Your service order is currently being processed by dispatch. A technician update will follow shortly."
    else:
        intent = "other"
        reply = "We have received your field event and our dispatch desk will review it shortly."

    return {
        "intent": intent,
        "suggested_reply": reply,
        "model": "mock-local-rule-engine",
        "latency_ms": round(latency_ms, 2),
        "tokens_used": 0
    }