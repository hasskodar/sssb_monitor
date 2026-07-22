import requests
import json
import re
import os

# ── KONFIGURATION ──────────────────────────────────────────────────────────────
# Lokalt: sätt dessa som miljövariabler ELLER ersätt strängarna direkt
# GitHub Actions: lägg dem som Secrets (Settings → Secrets → Actions)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "DIN_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "DIN_CHAT_ID")

# Fil där vi sparar kända lägenheter mellan körningar
STATE_FILE = "known_apartments.json"

# SSSB API-URL per område
AREAS = {
    "Domus": "https://minasidor.sssb.se/widgets/?omraden=Domus&callback=cb&widgets%5B%5D=objektlistabilder%40lagenheter&widgets%5B%5D=objektsummering%40lagenheter&widgets%5B%5D=paginering%40lagenheter",
    "Nyponet": "https://minasidor.sssb.se/widgets/?omraden=Nypone&callback=cb&widgets%5B%5D=objektlistabilder%40lagenheter&widgets%5B%5D=objektsummering%40lagenheter&widgets%5B%5D=paginering%40lagenheter",
}
# ──────────────────────────────────────────────────────────────────────────────


def fetch_apartments(url):
    """Hämtar aktuella lägenheter från SSSB:s API för ett givet område."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SSSB-monitor/1.0)",
        "Referer": "https://minasidor.sssb.se/lediga-bostader/",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    # API:t returnerar JSONP: cb({...}); – vi strippar wrapper-funktionen
    text = resp.text.strip()
    match = re.match(r"^[^(]+\((.+)\);?$", text, re.DOTALL)
    if not match:
        raise ValueError(f"Oväntat API-svar: {text[:200]}")

    data = json.loads(match.group(1))
    apartments = data.get("data", {}).get("objektlistabilder@lagenheter", [])
    return apartments


def load_known():
    """Läser sparade objektnummer från disk."""
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        return set(json.load(f))


def save_known(ids):
    """Sparar aktuella objektnummer till disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(list(ids), f)


def send_telegram(message):
    """Skickar ett meddelande via Telegram-boten."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def format_message(apt):
    """Formaterar ett snyggt Telegram-meddelande för en lägenhet."""
    url = apt.get("detaljUrl", "")
    area = apt.get("omrade", "SSSB")
    return (
        f"🏠 <b>Ny lägenhet på {area}!</b>\n"
        f"📍 {apt.get('adress', '?')}\n"
        f"🛏 {apt.get('typ', '?')}  |  {apt.get('yta', '?')} kvm  |  vån {apt.get('vaning', '?')}\n"
        f"💰 {apt.get('hyra', '?')} {apt.get('hyraEnhet', 'kr')}/mån\n"
        f"📅 Inflyttning: {apt.get('inflyttningDatum', '?')}\n"
        f"🔗 <a href=\"{url}\">Öppna på SSSB</a>"
    )


def main():
    known_ids = load_known()
    all_current_ids = set()

    for area_name, url in AREAS.items():
        print(f"Kollar {area_name}...")
        apartments = fetch_apartments(url)
        current_ids = {apt["objektNr"] for apt in apartments}
        all_current_ids.update(current_ids)

        new_apartments = [apt for apt in apartments if apt["objektNr"] not in known_ids]
        if new_apartments:
            print(f"  🚨 {len(new_apartments)} ny/nya i {area_name}!")
            for apt in new_apartments:
                msg = format_message(apt)
                send_telegram(msg)
                print(f"  Notis skickad: {apt['adress']}")
        else:
            print(f"  Inga nyheter. {len(apartments)} lägenhet(er) ute just nu.")

    save_known(all_current_ids)

if __name__ == "__main__":
    main()
