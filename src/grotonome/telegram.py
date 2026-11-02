"""Envoi Telegram. Le jeton n'est pas recopié dans les erreurs."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def send_message(text: str, token: str, chat_id: str, *, timeout: float = 20) -> tuple[bool, str]:
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False, f"Telegram HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"Telegram HTTP {exc.code}"
    except urllib.error.URLError:
        return False, "Telegram injoignable"
    return True, "envoyé"
