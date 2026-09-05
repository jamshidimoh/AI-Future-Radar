import html
import json
import os
import re
from urllib.parse import quote, urlparse, parse_qs
import requests

CATEGORY_EMOJI = {"ai": "🤖", "quantum": "⚛️", "genetics": "🧬", "mind": "🧠", "future": "🔮"}
TITLE_ICON = "📡"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
TELEGRAM_TEXT_LIMIT = 4096
PHOTO_CAPTION_LIMIT = 1024
RLI = "\u2067"
LRI = "\u2066"
PDI = "\u2069"
RLM = "\u200f"
NBSP = "\u00a0"


def _esc(text, quote=False):
    return html.escape(str(text or ""), quote=quote)


def _isolate_latin(text):
    raw = str(text or "")
    return re.sub(r"[A-Za-z][A-Za-z0-9@._+/#:&'’(),\-\s]*", lambda m: f"{LRI}{m.group(0).rstrip()}{PDI}{m.group(0)[len(m.group(0).rstrip()):]}", raw)


def _isolate_latin_html(text):
    parts = re.split(r"(<[^>]+>)", str(text or ""))
    return "".join(part if part.startswith("<") and part.endswith(">") else _isolate_latin(part) for part in parts)


def _rtl_text(text, *, escape=True, isolate_latin=True):
    raw = str(text or "")
    if escape:
        value = _isolate_latin(raw) if isolate_latin else raw
        value = _esc(value)
    else:
        value = _isolate_latin_html(raw) if isolate_latin else raw
    return f"{RLI}{value}{PDI}"


def _ltr_text(text, *, escape=True):
    value = str(text or "")
    return f"{LRI}{_esc(value) if escape else value}{PDI}"


def _chatgpt_link(title, link):
    compact_title = " ".join(str(title or "").split()).strip()
    compact_link = str(link or "").strip()
    prompt = (
        "لطفاً این مطلب را به فارسی و به‌صورت تحلیلی بررسی کن. "
        "مفاهیم پایه، موضوع اصلی، اهمیت، پیامدها و مسیر آینده را متناسب با همین مطلب توضیح بده و از کلی‌گویی پرهیز کن. "
        f"عنوان: {compact_title}\nمنبع: {compact_link}"
    )
    return "https://chatgpt.com/?q=" + quote(prompt, safe="")


def _gregorian_date(value):
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", str(value or ""))
    if not match:
        return ""
    y, m, d = match.groups()
    return f"{int(y):04d}/{int(m):02d}/{int(d):02d}"


def _model_name(summary_data):
    return str(summary_data.get("_provider") or summary_data.get("_provider_editorial") or summary_data.get("_provider_draft") or "").strip()


def _youtube_thumbnail(url):
    raw = str(url or "").strip()
    try:
        parsed = urlparse(raw)
        host = parsed.netloc.lower().split(":")[0]
        video_id = ""
        if host in {"youtu.be", "www.youtu.be"}:
            video_id = parsed.path.strip("/").split("/")[0]
        elif host.endswith("youtube.com"):
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
                parts = parsed.path.split("/")
                video_id = parts[2] if len(parts) > 2 else ""
        if re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id):
            return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    except Exception:
        pass
    return None


def _source_page_image(link):
    raw = str(link or "").strip()
    if not raw:
        return None
    thumb = _youtube_thumbnail(raw)
    if thumb:
        return thumb
    try:
        response = requests.get(raw, headers={"User-Agent": "Mozilla/5.0 (AI-Future-Radar image resolver)"}, timeout=12, allow_redirects=True)
        if response.status_code >= 400:
            return None
        html_text = response.text[:1_500_000]
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.I)
            if match:
                image = match.group(1).strip()
                if image.startswith("//"):
                    parsed = urlparse(response.url)
                    image = f"{parsed.scheme}:{image}"
                elif image.startswith("/"):
                    parsed = urlparse(response.url)
                    image = f"{parsed.scheme}://{parsed.netloc}{image}"
                return image
    except requests.RequestException as exc:
        print(f"[WARN] Source image resolver failed: {exc}", flush=True)
    except Exception as exc:
        print(f"[WARN] Source image parser failed: {exc}", flush=True)
    return None


def _image_signature_ok(prefix):
    if prefix.startswith(b"\xff\xd8\xff"):
        return True
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a"):
        return True
    return prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"


def _validate_remote_image(image_url):
    raw = str(image_url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        with requests.get(raw, headers={"User-Agent": "Mozilla/5.0 (AI-Future-Radar image validator)"}, timeout=12, stream=True, allow_redirects=True) as response:
            if response.status_code != 200:
                return False
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/") or content_type in {"image/svg+xml", "image/svg"}:
                return False
            prefix = next(response.iter_content(chunk_size=32), b"")
            if not _image_signature_ok(prefix):
                return False
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) < 256:
                return False
            return True
    except requests.RequestException as exc:
        print(f"[WARN] Image validation failed: {exc}", flush=True)
        return False
    except Exception as exc:
        print(f"[WARN] Image validation exception: {exc}", flush=True)
        return False


def format_post(summary_data, source_name, link, is_video=False, published="", content_type="news", source_tier=3, source_type="news", leader=""):
    title_raw = str(summary_data.get("title", "")).strip()
    summary_raw = str(summary_data.get("summary", "")).strip()
    why_raw = str(summary_data.get("why_it_matters", "")).strip()
    quote_raw = str(summary_data.get("key_quote", "")).strip()
    model = _model_name(summary_data)
    date = _gregorian_date(published)
    title_html = f"<b>{NBSP}{TITLE_ICON}{RLM} {title_raw}{RLM}</b>"
    lines = [_rtl_text(title_html, escape=False), "", _rtl_text(f"<blockquote>📌 <b>خلاصه</b>\n{_esc(summary_raw)}</blockquote>", escape=False)]
    if why_raw:
        lines += ["", _rtl_text(f"<blockquote>💡 <b>چرا مهم است؟</b>\n{_esc(why_raw)}</blockquote>", escape=False)]
    if quote_raw and content_type in {"interview", "podcast", "talk", "lecture", "conversation", "q&a"}:
        lines += ["", _rtl_text(f"<blockquote>💬 <b>نقل‌قول کلیدی</b>\n«{_esc(quote_raw)}»</blockquote>", escape=False)]
    source_name_clean = str(source_name or "منبع").strip()
    source_url = _esc(link, quote=True)
    source_row = _rtl_text(f"🏛 {source_name_clean}") if re.search(r"[\u0600-\u06ff]", source_name_clean) else _ltr_text(f"🏛 {source_name_clean}")
    source_link_row = _rtl_text(f"🔗 <a href=\"{source_url}\">مطالعه منبع اصلی</a>", escape=False)
    chatgpt_url = _esc(_chatgpt_link(title_raw, link), quote=True)
    chatgpt_row = _rtl_text(f"🧠 <a href=\"{chatgpt_url}\"><b>بررسی بیشتر با ChatGPT</b></a>", escape=False)
    lines += ["", DIVIDER, source_row, source_link_row, "", chatgpt_row]
    metadata_parts = []
    if model:
        metadata_parts.append(f"🤖 {_esc(model)}")
    if date:
        metadata_parts.append(f"🗓 {_esc(date)}")
    if metadata_parts:
        lines += ["", _rtl_text(f"<i>{'  ·  '.join(metadata_parts)}</i>", escape=False)]
    return "\n".join(lines)


def resolve_source_image(item):
    if not isinstance(item, dict):
        return ""
    candidates = [item.get("image_url"), item.get("thumbnail_url"), _source_page_image(item.get("link") or item.get("url") or "")]
    for candidate in candidates:
        image = str(candidate or "").strip()
        if image and _validate_remote_image(image):
            return image
    return ""


def _normalize_plain(text):
    text = re.sub(r'<a\s+href=["\'][^"\']+["\']>(.*?)</a>', r"\1", str(text or ""), flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _chunk_text(text, limit=TELEGRAM_TEXT_LIMIT):
    if len(text) <= limit:
        return [text]
    out, rest = [], text
    while len(rest) > limit:
        cut = rest.rfind("\n", 0, limit)
        if cut < 1:
            cut = limit
        out.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip("\n")
    if rest:
        out.append(rest)
    return out


def _result_metadata(response):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or not payload.get("ok"):
        print(f"[ERROR] Telegram send failed: {response.status_code} - {response.text}", flush=True)
        return False
    result = payload.get("result") or {}
    return {"ok": True, "chat_id": (result.get("chat") or {}).get("id"), "message_id": result.get("message_id"), "date": result.get("date"), "raw": result}


def _telegram_preflight(token, channel):
    base = f"https://api.telegram.org/bot{token}"
    try:
        chat_response = requests.get(f"{base}/getChat", params={"chat_id": channel}, timeout=15)
        chat_payload = chat_response.json()
        if chat_response.status_code != 200 or not chat_payload.get("ok"):
            print(f"[ERROR] Telegram destination verification failed: {chat_response.status_code} - {chat_response.text}", flush=True)
            return False
        chat = chat_payload.get("result") or {}
        print(f"[Telegram Destination] chat_id={chat.get('id')} type={chat.get('type')} title={chat.get('title') or chat.get('username') or ''}", flush=True)
        if chat.get("type") not in {"channel", "supergroup", "group"}:
            return False
        me_response = requests.get(f"{base}/getMe", timeout=15)
        me_payload = me_response.json()
        if me_response.status_code != 200 or not me_payload.get("ok"):
            return False
        bot_id = (me_payload.get("result") or {}).get("id")
        member_response = requests.get(f"{base}/getChatMember", params={"chat_id": chat.get("id"), "user_id": bot_id}, timeout=15)
        member_payload = member_response.json()
        if member_response.status_code != 200 or not member_payload.get("ok"):
            return False
        member = member_payload.get("result") or {}
        status = member.get("status")
        if chat.get("type") == "channel" and status not in {"administrator", "creator"}:
            return False
        if chat.get("type") == "channel" and status == "administrator" and member.get("can_post_messages") is False:
            return False
        return True
    except Exception as exc:
        print(f"[ERROR] Telegram destination verification exception: {exc}", flush=True)
        return False


def _valid_preview_url(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
    except Exception:
        return ""
    return raw


def _link_preview_options(preview_url="", *, enabled=True):
    raw = _valid_preview_url(preview_url)
    if not enabled or not raw:
        return {"is_disabled": True}
    return {
        "is_disabled": False,
        "url": raw,
        "prefer_large_media": True,
        "show_above_text": True,
    }


def _send_text_full(token, channel, text, *, preview_url="", preflight=True):
    if preflight and not _telegram_preflight(token, channel):
        return False
    chunks = _chunk_text(text)
    last = None
    for i, chunk in enumerate(chunks, 1):
        preview_enabled = i == 1 and bool(_valid_preview_url(preview_url))
        data = {
            "chat_id": channel,
            "text": chunk,
            "parse_mode": "HTML",
            "link_preview_options": json.dumps(
                _link_preview_options(preview_url, enabled=preview_enabled),
                ensure_ascii=False,
            ),
        }
        try:
            response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20)
        except requests.RequestException as exc:
            print(f"[ERROR] Telegram sendMessage transport failure; no retry to avoid duplicate publication: {exc}", flush=True)
            return False
        meta = _result_metadata(response)
        if not meta:
            if response.status_code in {400, 401, 403, 404}:
                fallback = {
                    "chat_id": channel,
                    "text": _normalize_plain(chunk),
                    "link_preview_options": json.dumps(
                        _link_preview_options(preview_url, enabled=preview_enabled),
                        ensure_ascii=False,
                    ),
                }
                try:
                    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=fallback, timeout=20)
                except requests.RequestException as exc:
                    print(f"[ERROR] Telegram plain-text fallback transport failure: {exc}", flush=True)
                    return False
                meta = _result_metadata(response)
            else:
                print("[ERROR] Telegram sendMessage result ambiguous; no fallback retry to avoid duplicate publication", flush=True)
        if not meta:
            return False
        print(f"[Telegram Published] chat_id={meta.get('chat_id')} message_id={meta.get('message_id')}", flush=True)
        last = meta
        if len(chunks) > 1:
            print(f"  ✓ Telegram text chunk {i}/{len(chunks)} sent", flush=True)
    return last


def _compact_photo_caption(text):
    from telegram_photo_contract import _compact_photo_caption as build_caption
    return build_caption(text)


def _send_source_image(token, channel, image_url, source_link="", title=""):
    image = str(image_url or "").strip()
    if not image or not _validate_remote_image(image):
        print(f"[Telegram Image] skipped: invalid/non-image URL: {image}", flush=True)
        return False
    caption = _compact_photo_caption(title) if title else ""
    if not caption:
        print("[Telegram Image] skipped: caption contract failed", flush=True)
        return False
    try:
        payload = {
            "chat_id": channel,
            "photo": image,
            "caption": caption[:950],
            "parse_mode": "HTML",
            "show_caption_above_media": False,
            "disable_notification": False,
        }
        response = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=payload, timeout=30)
        meta = _result_metadata(response)
        if meta:
            print(f"[Telegram Image Published] chat_id={meta.get('chat_id')} message_id={meta.get('message_id')}", flush=True)
            return meta
        return False
    except Exception as exc:
        print(f"[WARN] Telegram source image send failed: {exc}", flush=True)
        return False


def send_to_telegram(text, image_url="", source_link=""):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")
    if not _telegram_preflight(token, channel):
        return False
    resolved_image = str(image_url or "").strip()
    if resolved_image and not _validate_remote_image(resolved_image):
        resolved_image = ""
    if not resolved_image and source_link:
        candidate = _source_page_image(source_link)
        if candidate and _validate_remote_image(candidate):
            resolved_image = candidate
    if resolved_image:
        caption_source = text
        photo_result = _send_source_image(token, channel, resolved_image, source_link=source_link, title=caption_source)
        if photo_result:
            return photo_result
        print("[Telegram Image] photo delivery failed; falling back to canonical text", flush=True)
    return _send_text_full(token, channel, text, preview_url=source_link, preflight=False)


def send_to_telegram_safe(text, image_url="", source_link=""):
    try:
        return send_to_telegram(text, image_url=image_url, source_link=source_link)
    except Exception as exc:
        print(f"[ERROR] Telegram delivery exception: {exc}", flush=True)
        return False
