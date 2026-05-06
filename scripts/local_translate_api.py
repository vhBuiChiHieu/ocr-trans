from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MODEL_NAME = "translategemma:4b"
OLLAMA_TIMEOUT_SECONDS = 30

app = FastAPI(title="OCR Local Translate API", version="0.1.0")


@dataclass
class TranslateConfig:
    model: str = MODEL_NAME
    ollama_base_url: str = OLLAMA_BASE_URL
    timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS


CONFIG = TranslateConfig()


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_lang: str = Field(default="en", min_length=2, max_length=16)
    target_lang: str = Field(default="vi", min_length=2, max_length=16)
    preserve_newlines: bool = True


class TranslateResponse(BaseModel):
    translated_text: str
    source_lang: str
    target_lang: str
    model: str
    latency_ms: int


def _build_prompt(text: str, source_lang: str, target_lang: str, preserve_newlines: bool) -> str:
    newline_rule = (
        "Preserve line breaks exactly: same number of lines and newline positions."
        if preserve_newlines
        else "Keep natural formatting in target language."
    )
    return (
        f"Translate from {source_lang} to {target_lang}. "
        "Output only the translated text. No explanations, no quotes, no labels. "
        f"{newline_rule}\n"
        "Text:\n<<<BEGIN>>>\n"
        f"{text}\n"
        "<<<END>>>"
    )


def _ollama_generate(prompt: str) -> str:
    body = {
        "model": CONFIG.model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }
    request = Request(
        f"{CONFIG.ollama_base_url}/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=CONFIG.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama HTTP error: {exc.code}") from exc
    except URLError as exc:
        raise HTTPException(status_code=503, detail="Cannot reach Ollama on localhost:11434") from exc

    translated = (payload.get("response") or "").strip()
    if not translated:
        raise HTTPException(status_code=502, detail="Empty response from model")
    return translated


@app.get("/health")
def health() -> dict[str, object]:
    request = Request(f"{CONFIG.ollama_base_url}/api/tags", method="GET")
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return {
            "status": "degraded",
            "ollama_reachable": False,
            "model": CONFIG.model,
            "model_ready": False,
        }

    models = payload.get("models") or []
    model_names = {item.get("name") for item in models if isinstance(item, dict)}
    model_ready = CONFIG.model in model_names
    return {
        "status": "ok" if model_ready else "degraded",
        "ollama_reachable": True,
        "model": CONFIG.model,
        "model_ready": model_ready,
    }


@app.post("/v1/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest) -> TranslateResponse:
    start = time.perf_counter()
    prompt = _build_prompt(req.text, req.source_lang, req.target_lang, req.preserve_newlines)
    translated = _ollama_generate(prompt)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return TranslateResponse(
        translated_text=translated,
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        model=CONFIG.model,
        latency_ms=latency_ms,
    )
