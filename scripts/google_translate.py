import argparse
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UA = "Mozilla/5.0"
HOST = "https://translate.google.com.vn"
RPC_ID = "MkEWBc"
CACHE_TTL_SECONDS = 45 * 60
CACHE_PATH = Path(__file__).with_name("google_translate_web_tokens.json")


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": UA})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def load_cached_tokens(cache_path: Path = CACHE_PATH, ttl: int = CACHE_TTL_SECONDS) -> dict[str, str] | None:
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    saved_at = payload.get("saved_at")
    tokens = payload.get("tokens")
    if not isinstance(saved_at, (int, float)) or not isinstance(tokens, dict):
        return None

    if time.time() - saved_at >= ttl:
        return None

    if not tokens.get("f.sid") or not tokens.get("bl"):
        return None

    return {
        "f.sid": tokens["f.sid"],
        "bl": tokens["bl"],
        "at": tokens.get("at", ""),
    }


def save_cached_tokens(tokens: dict[str, str], cache_path: Path = CACHE_PATH) -> None:
    payload = {
        "saved_at": time.time(),
        "tokens": {
            "f.sid": tokens["f.sid"],
            "bl": tokens["bl"],
            "at": tokens.get("at", ""),
        },
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def parse_tokens(html: str) -> dict[str, str]:
    fsid = re.search(r'"FdrFJe":"(.*?)"', html)
    bl = re.search(r'"cfb2h":"(.*?)"', html)
    at = re.search(r'"SNlM0e":"(.*?)"', html)

    if not fsid or not bl:
        raise ValueError("cannot parse tokens")

    return {
        "f.sid": fsid.group(1),
        "bl": bl.group(1),
        "at": at.group(1) if at else "",
    }


def fetch_tokens() -> dict[str, str]:
    html = fetch_text(HOST + "/")
    return parse_tokens(html)


def get_tokens(force_refresh: bool = False) -> dict[str, str]:
    if not force_refresh:
        cached = load_cached_tokens()
        if cached:
            return cached

    tokens = fetch_tokens()
    save_cached_tokens(tokens)
    return tokens


def build_translate_payload(text: str, sl: str, tl: str) -> str:
    inner = [[text, sl, tl, 1, None, 2], []]
    return json.dumps([[[RPC_ID, json.dumps(inner), None, "generic"]]])


def post_translate_batchexecute(f_req: str, tokens: dict[str, str], reqid: int) -> str:
    query = {
        "rpcids": RPC_ID,
        "source-path": "/",
        "f.sid": tokens["f.sid"],
        "bl": tokens["bl"],
        "hl": "vi",
        "soc-app": "1",
        "soc-platform": "1",
        "soc-device": "1",
        "_reqid": str(reqid),
        "rt": "c",
    }
    form = {"f.req": f_req}
    if tokens.get("at") is not None:
        form["at"] = tokens["at"]

    request = Request(
        f"{HOST}/_/TranslateWebserverUi/data/batchexecute?{urlencode(query)}",
        data=urlencode(form).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "User-Agent": UA,
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def find_translate_payload(body: str):
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("[[") and RPC_ID in line:
            outer = json.loads(line)
            return json.loads(outer[0][2])
    raise ValueError("cannot parse translate response")


def clean_translated_text(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"(?<=\S)([.!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"(?<=\S)([.!?;:])(?=\))", r"\1", text)
    text = re.sub(r"(?<=\S)(\))(?=\S)", r"\1 ", text)
    text = re.sub(r" (?=[.!?;:])", "", text)
    text = re.sub(r" \)", ")", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def parse_translate_text(body: str) -> str:
    payload = find_translate_payload(body)
    try:
        segments = payload[1][0][0][5]
        parts = [segment[0] for segment in segments if isinstance(segment, list) and segment and segment[0]]
    except (TypeError, IndexError):
        raise ValueError("translated text path changed") from None

    if not parts:
        raise ValueError("translated text missing")

    return clean_translated_text("".join(parts))


def translate_text(text: str, sl: str = "en", tl: str = "vi", reqid: int | None = None) -> str:
    if reqid is None:
        reqid = int(time.time() * 1000) % 1000000

    f_req = build_translate_payload(text, sl, tl)

    for attempt in range(2):
        force_refresh = attempt == 1
        try:
            tokens = get_tokens(force_refresh=force_refresh)
            raw = post_translate_batchexecute(f_req, tokens, reqid)
            return parse_translate_text(raw)
        except (HTTPError, URLError, ValueError):
            if attempt == 1:
                raise

    raise RuntimeError("translation failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Text to translate")
    parser.add_argument("--sl", default="en", help="Source language, default: en")
    parser.add_argument("--tl", default="vi", help="Target language, default: vi")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    text = args.text.replace("\\n", "\n")
    print(translate_text(text, sl=args.sl, tl=args.tl))


if __name__ == "__main__":
    main()
