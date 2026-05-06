# Local Translate API Service

Run local translation API for OCR app using Ollama `translategemma:4b`.

## Run

```bash
.venv/Scripts/python.exe services/translate_api/run.py
```

Service URL: `http://127.0.0.1:8765`

## Endpoints

- `GET /health`
- `POST /v1/translate`

## Quick test

```bash
curl http://127.0.0.1:8765/health
```

```bash
curl -X POST http://127.0.0.1:8765/v1/translate -H "Content-Type: application/json" -d "{\"text\":\"Hello\\nHow are you?\",\"source_lang\":\"en\",\"target_lang\":\"vi\"}"
```
