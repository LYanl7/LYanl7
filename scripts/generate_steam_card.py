#!/usr/bin/env python3
"""Generate a self-contained Steam profile card for a GitHub README."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_ROOT = "https://api.steampowered.com"
USER_AGENT = "LYanl7 GitHub profile card"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def fetch_json(path: str, **params: object) -> dict:
    url = f"{API_ROOT}/{path}/?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def image_data_uri(url: str | None) -> str | None:
    if not url:
        return None
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=20) as response:
            payload = response.read(1_500_001)
            if len(payload) > 1_500_000:
                return None
            content_type = response.headers.get_content_type()
    except Exception:
        return None
    if not content_type.startswith("image/"):
        content_type = mimetypes.guess_type(url)[0] or "image/jpeg"
    return f"data:{content_type};base64,{base64.b64encode(payload).decode('ascii')}"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def shorten(value: object, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def hours(minutes: int | float | None) -> str:
    value = float(minutes or 0) / 60
    if value >= 1000:
        return f"{value / 1000:.2f}k hrs"
    if value >= 100:
        return f"{value:.0f} hrs"
    if value >= 10:
        return f"{value:.1f} hrs"
    return f"{value:.1f} hrs"


def date_text(timestamp: int | None) -> str:
    if not timestamp:
        return "Not available"
    return datetime.fromtimestamp(timestamp, SHANGHAI).strftime("%d %b %Y")


def load_live_data(steam_id: str, token: str) -> dict:
    players = fetch_json(
        "ISteamUser/GetPlayerSummaries/v2", key=token, steamids=steam_id
    ).get("response", {}).get("players", [])
    if not players:
        raise RuntimeError("Steam returned no public player profile")

    level = fetch_json(
        "IPlayerService/GetSteamLevel/v1", key=token, steamid=steam_id
    ).get("response", {}).get("player_level", 0)
    owned = fetch_json(
        "IPlayerService/GetOwnedGames/v1",
        key=token,
        steamid=steam_id,
        include_appinfo="false",
        include_played_free_games="true",
    ).get("response", {})
    recent = fetch_json(
        "IPlayerService/GetRecentlyPlayedGames/v1",
        key=token,
        steamid=steam_id,
        count=3,
    ).get("response", {}).get("games", [])

    return {
        "player": players[0],
        "level": level,
        "game_count": owned.get("game_count", len(owned.get("games", []))),
        "total_minutes": sum(game.get("playtime_forever", 0) for game in owned.get("games", [])),
        "recent": recent[:3],
    }


def demo_data(steam_id: str) -> dict:
    return {
        "player": {
            "steamid": steam_id,
            "personaname": "LYanl7",
            "personastate": 1,
            "profileurl": f"https://steamcommunity.com/profiles/{steam_id}/",
            "lastlogoff": 1788710400,
            "gameextrainfo": "Counter-Strike 2",
        },
        "level": 10,
        "game_count": 58,
        "total_minutes": 175800,
        "recent": [
            {"appid": 730, "name": "Counter-Strike 2", "playtime_forever": 107940, "playtime_2weeks": 420},
            {"appid": 2622380, "name": "ELDEN RING NIGHTREIGN", "playtime_forever": 14760, "playtime_2weeks": 180},
            {"appid": 477160, "name": "Human Fall Flat", "playtime_forever": 480, "playtime_2weeks": 60},
        ],
    }


def game_art(game: dict, demo: bool) -> str | None:
    if demo:
        return None
    app_id = game.get("appid")
    candidates = [
        f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg",
        f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
    ]
    icon_hash = game.get("img_icon_url")
    if icon_hash:
        candidates.append(
            f"https://media.steampowered.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
        )
    for candidate in candidates:
        result = image_data_uri(candidate)
        if result:
            return result
    return None


def render_card(data: dict, demo: bool) -> str:
    player = data["player"]
    recent = data["recent"]
    state = int(player.get("personastate", 0))
    in_game = bool(player.get("gameextrainfo"))
    status_names = {
        0: "Offline",
        1: "Online",
        2: "Busy",
        3: "Away",
        4: "Snooze",
        5: "Looking to trade",
        6: "Looking to play",
    }
    status = f"In-Game · {player['gameextrainfo']}" if in_game else status_names.get(state, "Offline")
    status_color = "#a4d007" if in_game else "#57cbde" if state else "#898989"
    avatar = None if demo else image_data_uri(player.get("avatarfull"))

    game_cards: list[str] = []
    for index, game in enumerate(recent[:3]):
        x = 32 + index * 262
        art = game_art(game, demo)
        image = (
            f'<image href="{art}" x="{x}" y="267" width="246" height="92" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#game-{index})"/>'
            if art
            else f'<rect x="{x}" y="267" width="246" height="92" rx="8" fill="url(#game-fallback)"/>'
        )
        recent_minutes = game.get("playtime_2weeks", 0)
        recent_label = f"{hours(recent_minutes)} past 2 weeks" if recent_minutes else f"Last played {date_text(game.get('rtime_last_played'))}"
        game_cards.append(
            f"""
    <g>
      <rect x="{x}" y="259" width="246" height="143" rx="10" fill="#16202d" stroke="#2b475e"/>
      {image}
      <rect x="{x}" y="323" width="246" height="36" fill="url(#art-fade)"/>
      <text x="{x + 14}" y="349" class="game-name">{esc(shorten(game.get('name', 'Unknown game'), 27))}</text>
      <text x="{x + 14}" y="378" class="game-meta">{esc(recent_label)}</text>
      <text x="{x + 232}" y="378" text-anchor="end" class="game-meta">{esc(hours(game.get('playtime_forever')))} total</text>
    </g>"""
        )

    if not game_cards:
        game_cards.append(
            '<rect x="32" y="259" width="782" height="143" rx="10" fill="#16202d" stroke="#2b475e"/>'
            '<text x="423" y="334" text-anchor="middle" class="empty">No recent games are publicly available</text>'
        )

    avatar_markup = (
        f'<image href="{avatar}" x="35" y="76" width="126" height="126" preserveAspectRatio="xMidYMid slice" clip-path="url(#avatar)"/>'
        if avatar
        else '<rect x="35" y="76" width="126" height="126" rx="8" fill="#22384d"/>'
    )
    total_hours = hours(data.get("total_minutes"))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="846" height="430" viewBox="0 0 846 430" role="img" aria-labelledby="title description">
  <title id="title">{esc(player.get('personaname', 'Steam'))}'s Steam profile</title>
  <desc id="description">Steam profile details and recently played games, generated from the Steam Web API.</desc>
  <defs>
    <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#101b2b"/>
      <stop offset="0.55" stop-color="#162b3f"/>
      <stop offset="1" stop-color="#0b141f"/>
    </linearGradient>
    <linearGradient id="header" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#1a9fff" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#66c0f4" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="game-fallback" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1a9fff"/>
      <stop offset="1" stop-color="#1b2838"/>
    </linearGradient>
    <linearGradient id="art-fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#16202d" stop-opacity="0"/>
      <stop offset="1" stop-color="#16202d"/>
    </linearGradient>
    <clipPath id="avatar"><rect x="35" y="76" width="126" height="126" rx="8"/></clipPath>
    <clipPath id="game-0"><rect x="32" y="267" width="246" height="92" rx="8"/></clipPath>
    <clipPath id="game-1"><rect x="294" y="267" width="246" height="92" rx="8"/></clipPath>
    <clipPath id="game-2"><rect x="556" y="267" width="246" height="92" rx="8"/></clipPath>
    <style>
      text {{ font-family: "Segoe UI", Arial, sans-serif; }}
      .label {{ fill: #8f98a0; font-size: 12px; letter-spacing: 1.4px; }}
      .value {{ fill: #d6d7d8; font-size: 20px; font-weight: 600; }}
      .game-name {{ fill: #ffffff; font-size: 15px; font-weight: 600; }}
      .game-meta {{ fill: #8f98a0; font-size: 11px; }}
      .empty {{ fill: #8f98a0; font-size: 16px; }}
    </style>
  </defs>
  <rect x="1" y="1" width="844" height="428" rx="14" fill="url(#background)" stroke="#29445c" stroke-width="2"/>
  <rect x="1" y="1" width="844" height="54" rx="14" fill="url(#header)"/>
  <path d="M31 28a13 13 0 1 0 26 0 13 13 0 0 0-26 0Zm19 0a6 6 0 1 1-12 0 6 6 0 0 1 12 0Zm3-8 15-9a9 9 0 1 1 4 7l-16 10" fill="none" stroke="#c7d5e0" stroke-width="3" stroke-linecap="round"/>
  <text x="87" y="35" fill="#c7d5e0" font-size="18" font-weight="700" letter-spacing="1.8">STEAM PROFILE</text>
  <text x="814" y="34" text-anchor="end" fill="#66c0f4" font-size="12">STEAMID · {esc(player.get('steamid', ''))}</text>

  <rect x="31" y="72" width="134" height="134" rx="11" fill="none" stroke="{status_color}" stroke-width="4"/>
  {avatar_markup}
  <text x="187" y="104" fill="#ffffff" font-size="28" font-weight="600">{esc(shorten(player.get('personaname', 'Steam'), 31))}</text>
  <circle cx="194" cy="130" r="5" fill="{status_color}"/>
  <text x="207" y="135" fill="{status_color}" font-size="15">{esc(shorten(status, 55))}</text>
  <text x="187" y="167" fill="#8f98a0" font-size="13">Last online · {esc(date_text(player.get('lastlogoff')))}</text>

  <g transform="translate(510 78)">
    <rect width="92" height="105" rx="9" fill="#192b3d" stroke="#29445c"/>
    <text x="46" y="28" text-anchor="middle" class="label">LEVEL</text>
    <text x="46" y="70" text-anchor="middle" class="value">{esc(data.get('level', 0))}</text>
  </g>
  <g transform="translate(612 78)">
    <rect width="92" height="105" rx="9" fill="#192b3d" stroke="#29445c"/>
    <text x="46" y="28" text-anchor="middle" class="label">GAMES</text>
    <text x="46" y="70" text-anchor="middle" class="value">{esc(data.get('game_count', 0))}</text>
  </g>
  <g transform="translate(714 78)">
    <rect width="100" height="105" rx="9" fill="#192b3d" stroke="#29445c"/>
    <text x="50" y="28" text-anchor="middle" class="label">PLAYTIME</text>
    <text x="50" y="70" text-anchor="middle" class="value">{esc(total_hours)}</text>
  </g>

  <line x1="32" y1="225" x2="814" y2="225" stroke="#29445c"/>
  <text x="32" y="247" class="label">RECENT ACTIVITY</text>
  {''.join(game_cards)}
  <text x="814" y="418" text-anchor="end" fill="#53697b" font-size="10">Updated automatically via Steam Web API</text>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steam-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if args.demo:
        data = demo_data(args.steam_id)
    else:
        token = os.environ.get("STEAM_TOKEN")
        if not token:
            raise SystemExit("STEAM_TOKEN is required")
        data = load_live_data(args.steam_id, token)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_card(data, args.demo), encoding="utf-8")


if __name__ == "__main__":
    main()
