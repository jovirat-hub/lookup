# ─────────────────────────────────────────────────────────────────────
#  bot.py  —  Telegram bot + MLBB Lookup engine (single file)
#  - Daily limit: 3 lookups per free user (admins + premium exempt)
#  - Queue for free users, instant for premium/admin
#  - Lookup engine adapted from ZY_DEVID1.py
#  - Up to 10 retries per lookup until login + account fetch succeeds
# ─────────────────────────────────────────────────────────────────────
import os
import sys
import time
import asyncio
import logging
import sqlite3
import random
import string
import html
import struct
import socket
import zlib
import datetime
import json as _json
from datetime import datetime as _dt, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum

import urllib3
import zstandard as zstd
from Crypto.Cipher import AES

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── CONFIG ───────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "8794930784:AAFu3Bw3JHNVaGK056DsX_g5Js7D5F62GTc")
ADMIN_IDS      = {int(x) for x in os.getenv("ADMIN_IDS", "8477982865").split(",")}
CHANNEL_ID     = int(os.getenv("CHANNEL_ID", "-1004382349032"))
OWNER_USERNAME = "@ZyronDevv"
DB_FILE = os.getenv("DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bot_lookup.db"
)

# ── SERVER CONFIG (from ZY_DEVID1.py — these are the working values) ──
LOGIN_HOST     = "login.ml.youngjoygame.com"
LOGIN_PORT     = 30021
CLIENT_VERSION = "2.2.16.1232.1"
CHANNEL        = "and_usa"

# ── DAILY LIMIT CONFIG ───────────────────────────────────────────────
DAILY_FREE_LIMIT = 3
DAILY_RESET_TZ   = timezone.utc

# ── LOOKUP RETRY CONFIG ──────────────────────────────────────────────
MAX_LOOKUP_RETRIES = 10

# ── LOGGING ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lookup_bot")

# ═════════════════════════════════════════════════════════════════════
#  LOOKUP ENGINE  (adapted from ZY_DEVID1.py)
# ═════════════════════════════════════════════════════════════════════

DEBUG_MODE   = False

def dbg(label, data=None):
    if not DEBUG_MODE:
        return
    ts = _dt.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[DBG {ts}] {label}")
    if data is None:
        return
    if isinstance(data, (bytes, bytearray)):
        hex_str = data.hex()
        for i in range(0, len(hex_str), 64):
            print(f"  {hex_str[i:i+64]}")
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"  [{k}] => {repr(v)[:120]}")
    else:
        print(f"  {repr(data)[:200]}")


HERO_ID_MAP = {
    1: "Miya", 2: "Balmond", 3: "Saber", 4: "Alice", 5: "Nana", 6: "Tigreal",
    7: "Alucard", 8: "Karina", 9: "Akai", 10: "Franco", 11: "Bane", 12: "Bruno",
    13: "Clint", 14: "Rafaela", 15: "Eudora", 16: "Zilong", 17: "Fanny",
    18: "Layla", 19: "Minotaur", 20: "Lolita", 21: "Hayabusa", 22: "Freya",
    23: "Gord", 24: "Natalia", 25: "Kagura", 26: "Chou", 27: "Sun", 28: "Alpha",
    29: "Ruby", 30: "Yi Sun-shin", 31: "Moskov", 32: "Johnson", 33: "Cyclops",
    34: "Estes", 35: "Hilda", 36: "Aurora", 37: "Lapu-Lapu", 38: "Vexana",
    39: "Roger", 40: "Karrie", 41: "Gatotkaca", 42: "Harley", 43: "Irithel",
    44: "Grock", 45: "Argus", 46: "Odette", 47: "Lancelot", 48: "Diggie",
    49: "Hylos", 50: "Zhask", 51: "Helcurt", 52: "Pharsa", 53: "Lesley",
    54: "Jawhead", 55: "Angela", 56: "Gusion", 57: "Valir", 58: "Martis",
    59: "Uranus", 60: "Hanabi", 61: "Chang'e", 62: "Kaja", 63: "Selena",
    64: "Aldous", 65: "Claude", 66: "Vale", 67: "Leomord", 68: "Lunox",
    69: "Hanzo", 70: "Belerick", 71: "Kimmy", 72: "Thamuz", 73: "Harith",
    74: "Minsitthar", 75: "Kadita", 76: "Faramis", 77: "Badang", 78: "Khufra",
    79: "Granger", 80: "Guinevere", 81: "Esmeralda", 82: "Terizla", 83: "X.Borg",
    84: "Ling", 85: "Dyrroth", 86: "Lylia", 87: "Baxia", 88: "Masha",
    89: "Wanwan", 90: "Silvanna", 91: "Cecilion", 92: "Carmilla", 93: "Atlas",
    94: "Popol and Kupa", 95: "Yu Zhong", 96: "Luo Yi", 97: "Benedetta",
    98: "Khaleed", 99: "Barats", 100: "Brody", 101: "Yve", 102: "Mathilda",
    103: "Paquito", 104: "Gloo", 105: "Beatrix", 106: "Phoveus", 107: "Natan",
    108: "Aulus", 109: "Aamon", 110: "Valentina", 111: "Edith", 112: "Floryn",
    113: "Yin", 114: "Melissa", 115: "Xavier", 116: "Julian", 117: "Fredrinn",
    118: "Joy", 119: "Novaria", 120: "Arlott", 121: "Ixia", 122: "Nolan",
    123: "Cici", 124: "Chip", 125: "Zhuxin", 126: "Suyou", 127: "Lukas",
    128: "Kalea", 129: "Zetian", 130: "Obsidia",
}

# ── SKIN DB ──────────────────────────────────────────────────────────
_SKIN_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skin_db.json")
try:
    with open(_SKIN_DB_PATH, "r", encoding="utf-8") as _f:
        _raw = _f.read().strip()
        if not _raw.startswith("{"):
            _raw = "{" + _raw
        SKIN_DB = _json.loads(_raw)
except Exception:
    SKIN_DB = {}

SKIN_TIER_LABELS = {
    "common": "Common", "exceptional": "Exceptional", "deluxe": "Deluxe",
    "exquisite": "Exquisite", "grand": "Grand", "supreme": "Supreme",
    "unknown": "Unknown",
}

def get_skin_tier(skin_id):
    tier = SKIN_DB.get(str(skin_id))
    if not tier:
        return None
    return SKIN_TIER_LABELS.get(tier, tier.capitalize())

def get_hero_history(tag_91):
    return [HERO_ID_MAP.get(hid, f"Unknown({hid})") for hid in reversed(tag_91)]

def map_collector_point(point: int) -> str:
    if point < 1000:
        return "No Tier"
    tiers = [
        (1000, 4000, "Amateur Collector"), (4000, 10000, "Junior Collector"),
        (10000, 22000, "Seasoned Collector"), (22000, 44000, "Expert Collector"),
        (44000, 84000, "Renowned Collector"), (84000, 160000, "Exalted Collector"),
        (160000, 280000, "Mega Collector"), (280000, float("inf"), "World Collector"),
    ]
    for min_p, max_p, name in tiers:
        if min_p <= point < max_p:
            if name == "World Collector":
                return name
            per_level = (max_p - min_p) / 5
            level = int((point - min_p) // per_level)
            roman = ["V", "IV", "III", "II", "I"][level]
            return f"{name} {roman}"
    return "Unknown"

def map_rank(p):
    RANK_DEFINITIONS = [
        {"min": 0,   "max": 4,   "rank": "Warrior III"}, {"min": 5,   "max": 9,   "rank": "Warrior II"},
        {"min": 10,  "max": 14,  "rank": "Warrior I"},   {"min": 15,  "max": 19,  "rank": "Elite IV"},
        {"min": 20,  "max": 24,  "rank": "Elite III"},   {"min": 25,  "max": 29,  "rank": "Elite II"},
        {"min": 30,  "max": 34,  "rank": "Elite I"},     {"min": 35,  "max": 39,  "rank": "Master IV"},
        {"min": 40,  "max": 44,  "rank": "Master III"},  {"min": 45,  "max": 49,  "rank": "Master II"},
        {"min": 50,  "max": 54,  "rank": "Master I"},    {"min": 55,  "max": 59,  "rank": "Grandmaster IV"},
        {"min": 60,  "max": 64,  "rank": "Grandmaster III"}, {"min": 65, "max": 69, "rank": "Grandmaster II"},
        {"min": 70,  "max": 74,  "rank": "Grandmaster I"},   {"min": 75, "max": 81, "rank": "Epic IV"},
        {"min": 82,  "max": 88,  "rank": "Epic III"},    {"min": 89,  "max": 95,  "rank": "Epic II"},
        {"min": 96,  "max": 107, "rank": "Epic I"},      {"min": 108, "max": 114, "rank": "Legend IV"},
        {"min": 115, "max": 121, "rank": "Legend III"},  {"min": 122, "max": 128, "rank": "Legend II"},
        {"min": 129, "max": 135, "rank": "Legend I"},
        {"min": 136, "max": 160, "rank": lambda p: f"Mythic {p - 135}"},
        {"min": 161, "max": 195, "rank": lambda p: f"Mythical Honor {p - 135}"},
        {"min": 196, "max": 235, "rank": lambda p: f"Mythical Glory {p - 195}"},
        {"min": 236, "max": 999, "rank": lambda p: f"Mythical Immortal {p - 235}"},
    ]
    for entry in RANK_DEFINITIONS:
        if entry["min"] <= p <= entry["max"]:
            rank = entry["rank"]
            return rank(p) if callable(rank) else rank
    return "Unknown"

# ── BAN DETECTION ───────────────────────────────────────────────────
BAN_REASONS = {
    "1":  "Verbal Abuse / Inappropriate Avatar or Name",
    "2":  "Toxic Behavior / In-Game Chat Violation",
    "3":  "Intentional Feeding / AFK / Griefing",
    "7":  "Illegal Diamond Top-up / Refund Fraud",
    "21": "Using Plug-in Apps to Compromise Competitive Fairness",
    "22": "Account Security Risk / Fraudulent Activity",
    "23": "Unauthorized Account Access",
    "24": "Cheating in Ranked Match",
    "25": "Payment Fraud / Chargeback",
    "26": "Account Trading / Sale",
    "88": "Device Hardware Ban (HWID)",
    "99": "Permanent System Security Violation",
}

def _walk_ban(obj, out, depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()
            if k == "ban_reason":
                code = str(v)
                if code and code not in ("0", "", "None"):
                    out.setdefault("ban_code", code)
                    out.setdefault("reason_name", BAN_REASONS.get(
                        code, "Using Plug-in Apps to Compromise Competitive Fairness"))
            elif k == "endtime_day":
                if v is None:
                    continue
                try:
                    iv = int(v)
                except (TypeError, ValueError):
                    iv = None
                if iv is None:
                    out["endtime_day"] = v
                elif iv > 0:
                    out["endtime_day"] = iv
                else:
                    out.setdefault("endtime_day", 0)
            elif k == "endtime_hour":
                if v not in (None, 0, "0", ""):
                    out["endtime_hour"] = v
            elif k == "endtime_min":
                if v not in (None, 0, "0", ""):
                    out["endtime_min"] = v
            elif k == "endtime_sec":
                if v not in (None, 0, "0", ""):
                    out["endtime_sec"] = v
            elif k == "ban_status" or "ban_status" in k_lower:
                if isinstance(v, (dict, list)):
                    pass
                elif v not in (None, 0, False, "0", ""):
                    out["ban_status_raw"] = v
            elif k_lower.startswith("ban_") and k not in ("ban_reason", "ban_status"):
                if isinstance(v, (dict, list)):
                    pass
                elif v not in (None, 0, False, "0", ""):
                    out.setdefault(str(k), v)
            if isinstance(v, (dict, list)):
                _walk_ban(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_ban(item, out, depth + 1)

def _looks_like_player(sdp):
    if not sdp:
        return False
    try:
        nick = sdp.get(2)
        lvl  = sdp.get(3)
        cc   = sdp.get(97)
        loc  = sdp.get(71)
        if isinstance(nick, str) and len(nick.strip()) > 0:
            return True
        if isinstance(lvl, int) and lvl > 0:
            return True
        if isinstance(cc, str) and len(cc.strip()) > 0:
            return True
        if isinstance(loc, list) and len(loc) >= 2:
            return True
    except Exception:
        return False
    return False

def inspect_ban(sdp):
    info = {}
    if sdp:
        try:
            _walk_ban(dict(sdp), info)
        except Exception:
            pass

    if not _looks_like_player(sdp):
        raw = info.get("ban_status_raw")
        if raw is not None and str(raw).strip().lower() in ("1", "true", "yes", "banned", "ban"):
            info.setdefault("ban_code", "21")
            info.setdefault("reason_name", BAN_REASONS["21"])
            return True, info
        return False, {}

    banned = False
    day = info.get("endtime_day")
    has_hms = any(
        info.get(f"endtime_{u}") not in (None, 0, "0", "")
        for u in ("hour", "min", "sec")
    )

    if day is not None:
        try:
            d = int(day)
        except (TypeError, ValueError):
            d = None
        if d is not None:
            if d > 1_000_000_000:
                banned = True
            elif d > 0:
                banned = True
            elif d == 0 and has_hms:
                h = int(info.get("endtime_hour", 0) or 0)
                m = int(info.get("endtime_min", 0) or 0)
                s = int(info.get("endtime_sec", 0) or 0)
                total = h * 3600 + m * 60 + s
                if 0 < total <= 24 * 3600 and h <= 23:
                    banned = True
        else:
            if has_hms:
                banned = True

    if not banned:
        raw = info.get("ban_status_raw")
        if raw is not None and str(raw).strip().lower() in ("1", "true", "yes", "banned", "ban"):
            banned = True
            info.setdefault("ban_code", "21")
            info.setdefault("reason_name", BAN_REASONS["21"])

    if banned:
        if not info.get("reason_name"):
            code = info.get("ban_code") or "21"
            info["ban_code"] = code
            info["reason_name"] = BAN_REASONS.get(
                code, "Using Plug-in Apps to Compromise Competitive Fairness")
        return True, info
    return False, {}

def format_timestamp(timestamp):
    try:
        utc_dt = _dt.fromtimestamp(timestamp, timezone.utc)
        pht_dt = utc_dt + timedelta(hours=8)
        pht_date_str = pht_dt.strftime("%Y-%m-%d %H:%M")
        now_pht = _dt.now(timezone.utc) + timedelta(hours=8)
        delta = pht_dt - now_pht
        total_seconds = int(delta.total_seconds())
        if total_seconds >= 0:
            days    = total_seconds // 86400
            hours   = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            rel_str = f"(in {days}d {hours}h {minutes}m)"
        else:
            total_seconds = abs(total_seconds)
            days    = total_seconds // 86400
            hours   = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            rel_str = f"({days}d {hours}h {minutes}m ago)"
        return f"{pht_date_str} {rel_str} PHT"
    except Exception:
        return "Invalid timestamp"

def format_timestamp_full(timestamp):
    try:
        utc_dt = _dt.fromtimestamp(timestamp, timezone.utc)
        pht_dt = utc_dt + timedelta(hours=8)
        return pht_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid timestamp"

def format_ban_duration(info):
    day = info.get("endtime_day")
    if day is None:
        return None
    h = int(info.get("endtime_hour", 0) or 0)
    m = int(info.get("endtime_min", 0) or 0)
    s = int(info.get("endtime_sec", 0) or 0)
    try:
        d = int(day)
    except (TypeError, ValueError):
        return None
    if d > 1_000_000_000:
        return f"until {format_timestamp_full(d)}"
    if d > 0:
        return f"{d}d {h:02d}h {m:02d}m"
    total = h * 3600 + m * 60 + s
    if 0 < total <= 24 * 3600 and h <= 23:
        return f"{h:02d}h {m:02d}m {s:02d}s"
    return None

def extract_bindings(player_data):
    binds = []
    for tag, keys in (
        ("Facebook", (100, 101, 102, 110)),
        ("Google",   (103, 104, 111)),
        ("TikTok",   (105, 112)),
        ("Moonton",  (9, 11, 12, 13)),
        ("Apple",    (106, 113)),
        ("VK",       (107,)),
        ("Telegram", (108,)),
    ):
        for k in keys:
            v = player_data.get(k)
            if v is None:
                continue
            if isinstance(v, (str, int)) and str(v).strip() not in ("", "0"):
                binds.append(tag)
                break
            if isinstance(v, (dict, list)) and v:
                binds.append(tag)
                break
    for v in player_data.values():
        if not isinstance(v, str):
            continue
        low = v.lower()
        if "@" in v and "." in v.split("@")[-1] and len(v) < 80 and "Mail" not in binds:
            binds.append("Mail")
        if "facebook" in low and "Facebook" not in binds: binds.append("Facebook")
        if "google" in low and "Google" not in binds:     binds.append("Google")
        if "tiktok" in low and "TikTok" not in binds:     binds.append("TikTok")
        if "apple" in low and "Apple" not in binds:       binds.append("Apple")
    return ", ".join(dict.fromkeys(binds)) if binds else "Device Only"

# ── SDP ─────────────────────────────────────────────────────────────
class SdpDataType(Enum):
    INTEGER_POSITIVE = 0
    INTEGER_NEGATIVE = 1
    FLOAT = 2
    DOUBLE = 3
    STRING = 4
    LIST = 5
    DICT = 6
    STRUCT_BEGIN = 7
    STRUCT_END = 8

class SdpException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class SdpStruct(dict):
    def __init__(self, data=None):
        super().__init__()
        self.data = b""
        self.offset = 0
        if isinstance(data, bytes):
            self.data = data
            self.offset = 0
            self._unpack_from_binary()
        elif data is not None:
            super().update(data)
            self._pack_to_binary()

    def _pack_to_binary(self):
        self.data = bytes([SdpDataType.STRUCT_BEGIN.value << 4])
        for tag, value in sorted(self.items()):
            self._pack(tag, value)
        self.data += bytes([SdpDataType.STRUCT_END.value << 4])

    def _unpack_from_binary(self):
        if not self.data:
            return
        if self.data[0] >> 4 == SdpDataType.STRUCT_BEGIN.value:
            self.offset = 1
        while self.offset < len(self.data):
            tag, value = self._unpack()
            if isinstance(value, SdpDataType) and value == SdpDataType.STRUCT_END:
                break
            self[tag] = value

    def _write_number(self, value: int) -> bytes:
        result = bytearray()
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    def _read_number(self) -> int:
        n = 1
        val = self.data[self.offset] & 0x7F
        while self.data[self.offset + n - 1] >= 0x80:
            val |= (self.data[self.offset + n] & 0x7F) << (7 * n)
            n += 1
        self.offset += n
        return val

    def _pack_header(self, tag: int, data_type: SdpDataType) -> None:
        if tag < 15:
            self.data += bytes([(data_type.value << 4) | tag])
        else:
            self.data += bytes([(data_type.value << 4) | 15])
            self.data += self._write_number(tag)

    def _pack(self, tag: int, value: Any) -> None:
        if isinstance(value, bool):
            self._pack_header(tag, SdpDataType.INTEGER_POSITIVE)
            self.data += self._write_number(1 if value else 0)
        elif isinstance(value, int):
            if value < 0:
                self._pack_header(tag, SdpDataType.INTEGER_NEGATIVE)
                self.data += self._write_number(-value)
            else:
                self._pack_header(tag, SdpDataType.INTEGER_POSITIVE)
                self.data += self._write_number(value)
        elif isinstance(value, float):
            self._pack_header(tag, SdpDataType.DOUBLE)
            packed = struct.pack("<d", value)
            self.data += self._write_number(len(packed))
            self.data += packed
        elif isinstance(value, str) or isinstance(value, bytes):
            self._pack_header(tag, SdpDataType.STRING)
            encoded = value.encode("utf-8") if isinstance(value, str) else value
            self.data += self._write_number(len(encoded))
            self.data += encoded
        elif isinstance(value, list):
            self._pack_header(tag, SdpDataType.LIST)
            self.data += self._write_number(len(value))
            for item in value:
                self._pack(0, item)
        elif isinstance(value, dict):
            if isinstance(value, SdpStruct):
                self._pack_header(tag, SdpDataType.STRUCT_BEGIN)
                for k, v in sorted(value.items()):
                    self._pack(k, v)
                self.data += bytes([SdpDataType.STRUCT_END.value << 4])
            else:
                self._pack_header(tag, SdpDataType.DICT)
                self.data += self._write_number(len(value))
                for k, v in sorted(value.items()):
                    self._pack(0, k)
                    self._pack(0, v)
        else:
            raise SdpException(f"Unsupported type: {type(value)}")

    def _unpack(self) -> Tuple[int, Any]:
        try:
            if self.offset >= len(self.data):
                return 0, None
            header = self.data[self.offset]
            tag = header & 0xF
            data_type = SdpDataType(header >> 4)
            self.offset += 1
            if tag == 15:
                tag = self._read_number()
            if data_type == SdpDataType.INTEGER_POSITIVE:
                return tag, self._read_number()
            elif data_type == SdpDataType.INTEGER_NEGATIVE:
                return tag, -self._read_number()
            elif data_type == SdpDataType.FLOAT:
                value = self._read_number().to_bytes(4, "little")
                return tag, struct.unpack("<f", value)[0]
            elif data_type == SdpDataType.DOUBLE:
                value = self._read_number().to_bytes(8, "little")
                return tag, struct.unpack("<d", value)[0]
            elif data_type == SdpDataType.STRING:
                length = self._read_number()
                try:
                    value = self.data[self.offset:self.offset + length].decode("utf-8")
                except UnicodeDecodeError:
                    value = self.data[self.offset:self.offset + length]
                self.offset += length
                return tag, value
            elif data_type == SdpDataType.LIST:
                length = self._read_number()
                value = []
                for _ in range(length):
                    _, item = self._unpack()
                    value.append(item)
                return tag, value
            elif data_type == SdpDataType.DICT:
                length = self._read_number()
                value = {}
                for _ in range(length):
                    _, k = self._unpack()
                    _, v = self._unpack()
                    value[k] = v
                return tag, value
            elif data_type == SdpDataType.STRUCT_BEGIN:
                struct_data = {}
                while True:
                    sub_tag, sub_value = self._unpack()
                    if isinstance(sub_value, SdpDataType) and sub_value == SdpDataType.STRUCT_END:
                        break
                    struct_data[sub_tag] = sub_value
                return tag, SdpStruct(struct_data)
            elif data_type == SdpDataType.STRUCT_END:
                return tag, SdpDataType.STRUCT_END
            else:
                raise SdpException("Unknown data type")
        except Exception:
            raise SdpException("Unpack error")

    def __repr__(self):
        return f"SdpStruct({dict(self)})"

    def copy(self):
        return SdpStruct(super().copy())

    def update(self, other):
        super().update(other)
        self._pack_to_binary()

# ── DEVICE POOL (from ZY_DEVID1.py — verified working pool) ─────────
DEVICE_IDS = [
    "and_cd9e459ea708a948d5c2f5a6ca8838cf648efdbc9a8c3ce703fa556d-34a4-4cde-a061-34938d08a26e",
]

DEVICE_MODELS = [
    "Xiaomi:23049PCD8G", "Xiaomi:2201123G", "Xiaomi:22011211C", "Xiaomi:2211133C",
    "Xiaomi:23078PND5G", "Xiaomi:22101316G", "Xiaomi:Redmi Note 12", "Xiaomi:Redmi Note 12 Pro",
    "Xiaomi:Redmi Note 11", "Xiaomi:Redmi 12C", "Xiaomi:Redmi 10", "Xiaomi:Mi 11",
    "Xiaomi:Mi 11 Ultra", "Xiaomi:23013RK75G", "Xiaomi:2304FPN6DG", "Xiaomi:23054RA19I",
    "Xiaomi:22071219CG", "Xiaomi:2206123SC",
]

def load_device_ids():
    if not DEVICE_IDS:
        return ["and_cd9e459ea708a948d5c2f5a6ca8838cf648efdbc9a8c3ce703fa556d-34a4-4cde-a061-34938d08a26e"]
    return DEVICE_IDS.copy()

def load_device_models():
    if not DEVICE_MODELS:
        return ["Xiaomi:Redmi Note 12"]
    return DEVICE_MODELS.copy()

def remove_failed_device_id(failed_device_id):
    global DEVICE_IDS
    if failed_device_id in DEVICE_IDS:
        DEVICE_IDS.remove(failed_device_id)
        return True
    return False

AES_KEY = bytes.fromhex("f5a193d50ade553e9835595f5cd75ddd")
AES_IV  = b"\x00" * 16

def _aes_decrypt(data):
    if not data or len(data) % 16:
        raise SdpException(f"bad cipher length {len(data) if data else 0}")
    return AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV).decrypt(data).rstrip(b"\x00")

# ── DNS cache ────────────────────────────────────────────────────────
_DNS_CACHE = {}
_DNS_LOCK  = __import__("threading").Lock()

def _resolve(host):
    if not host:
        return host
    if host.replace(".", "").isdigit():
        return host
    now = time.time()
    with _DNS_LOCK:
        hit = _DNS_CACHE.get(host)
        if hit and hit[1] > now:
            return hit[0]
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        ip = host
    with _DNS_LOCK:
        _DNS_CACHE[host] = (ip, now + 600)
    return ip

# ── CONNECTIONS ─────────────────────────────────────────────────────
class GameConnection:
    def __init__(self, device_id, device_model=None):
        self.device_id = device_id
        self.device_model = device_model or "Xiaomi:Redmi Note 12"
        self.host = LOGIN_HOST
        self.port = LOGIN_PORT
        self.sequence = 1
        self.socket = None
        self.queue_data = b""
        self.last_header_size = 0
        self.ban_seen = False
        self.ban_info = {}

        parts = device_id.split("_")
        if len(parts) >= 2:
            device_info = parts[1]
            if len(parts) >= 3 and len(device_info) < 32:
                device_info = device_info + "_" + parts[2]
            if len(device_info) >= 32:
                self.imei_md5 = device_info[:32]
                if len(device_info) >= 48:
                    self.android_id = device_info[32:48]
                    self.advertising_id = device_info[48:] if len(device_info) > 48 else ""
                else:
                    self.android_id = ""
                    self.advertising_id = ""
            else:
                self.imei_md5 = device_info
                self.android_id = ""
                self.advertising_id = ""
        else:
            self.imei_md5 = device_id
            self.android_id = ""
            self.advertising_id = ""

        self.account_id = 0
        self.session_key = ""
        self.zone_id = 0
        self.game_server_host = ""
        self.game_server_port = 0
        self.creation_ts = 0

    def __enter__(self):
        self.connect(self.host, self.port)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()

    def connect(self, host=None, port=None):
        if host:
            self.host = host
        if port:
            self.port = port
        ip = _resolve(self.host)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass
        self.socket.settimeout(3)
        self.socket.connect((ip, self.port))

    def cleanup(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.sequence = 1
            self.socket = None
            self.queue_data = b""

    def close(self):
        self.cleanup()

    def _sniff(self, res):
        if self.ban_seen or res is None:
            return
        try:
            banned, info = inspect_ban(res)
        except Exception:
            return
        if banned:
            self.ban_seen = True
            self.ban_info = dict(info)

    def send_data(self, pid, sdp):
        packet = SdpStruct({0: pid, 1: self.sequence, 5: sdp.data}).data
        buf = zstd.compress(packet)
        flags = (len(buf) + 4) | (16 << 24)
        buf = flags.to_bytes(4, "big") + buf
        self.socket.sendall(buf)
        self.sequence += 1

    def recv_data(self):
        try:
            while len(self.queue_data) < 4:
                data = self.socket.recv(4096)
                if not data:
                    return None, None
                self.queue_data += data
            flags = int.from_bytes(self.queue_data[:4], "big")
            size = flags & 0xFFFFFF
            compression_type = flags >> 24
            self.last_header_size = size
            while len(self.queue_data) < size:
                data = self.socket.recv(4096)
                if not data:
                    return None, None
                self.queue_data += data
            data = self.queue_data[4:size]
            self.queue_data = self.queue_data[size:]
            if compression_type == 1:
                data = zlib.decompress(data)
            elif compression_type == 16:
                data = zstd.decompress(data)
            elif compression_type == 2:
                data = _aes_decrypt(data)
            elif compression_type == 3:
                data = zlib.decompress(_aes_decrypt(data))
            elif compression_type == 18:
                data = zstd.decompress(_aes_decrypt(data))
            result = SdpStruct(data)
            pid = result[0]
            if pid is None:
                return None, None
            res = result.get(6, None)
            if not res or not isinstance(res, bytes):
                res = result.get(5, None)
                if not res or not isinstance(res, bytes):
                    try:
                        self._sniff(result)
                    except Exception:
                        pass
                    return pid, None
            parsed_res = SdpStruct(res)
            try:
                self._sniff(parsed_res)
                self._sniff(result)
            except Exception:
                pass
            return pid, parsed_res
        except socket.timeout:
            return -1, None
        except Exception:
            return None, None

    # ── protocol steps (same as ZY_DEVID1.py) ──
    def login(self):
        self.connect(LOGIN_HOST, LOGIN_PORT)
        self.send_data(1, SdpStruct({
            0: self.device_id,
            1: f"gps_adid={self.advertising_id}&android_id={self.android_id}&device_unique_id={self.imei_md5}",
            2: CLIENT_VERSION,
            3: CHANNEL,
            4: "en",
        }))
        pid, res = self.recv_data()
        if pid == 2 and res:
            self.account_id = res.get(0)
            self.session_key = res.get(1)
            zd = res.get(2)
            if isinstance(zd, dict):
                self.zone_id = zd.get(0, 0)
            elif isinstance(zd, list) and zd:
                self.zone_id = zd[0] if not isinstance(zd[0], dict) else zd[0].get(0, 0)
            else:
                self.zone_id = zd or 0
            self.creation_ts = res.get(19, 0)
            return True, res
        return False, res

    def get_server(self):
        self.send_data(5, SdpStruct({
            0: self.account_id, 1: self.session_key, 2: CLIENT_VERSION,
            5: self.zone_id, 6: CHANNEL,
        }))
        pid, res = self.recv_data()
        if pid == 6 and res:
            addr = res[1]
            self.game_server_host, port_str = addr.split(":")
            self.game_server_port = int(port_str)
            return True, res
        return False, res

    def enter_game(self):
        self.cleanup()
        self.connect(self.game_server_host, self.game_server_port)
        self.send_data(10001, SdpStruct({
            0: self.account_id, 1: self.session_key, 2: self.zone_id,
            4: CLIENT_VERSION, 13: CHANNEL, 15: self.device_id,
        }))
        self.send_data(10101, SdpStruct({0: 0, 2: 2}))

    def handshake(self, tries=10):
        for _ in range(tries):
            pid, _ = self.recv_data()
            if pid is None or pid == -1:
                return False
            if pid == 10002:
                return True
        return False

    def lookup_player(self, search_value, search_type="id", server_filter=None):
        if search_type == "id":
            try:
                lookup_data = SdpStruct({1: int(search_value)})
            except (TypeError, ValueError):
                return None
        else:
            lookup_data = SdpStruct({0: str(search_value).strip()})
        self.send_data(11153, lookup_data)
        id_20001_count = 0
        while True:
            pid, res = self.recv_data()
            if pid is None:
                return None
            elif pid == -1:
                return None
            elif pid == 11154:
                if search_type == "nickname" and server_filter is not None:
                    return self.filter_by_server(res, server_filter)
                return res
            elif pid == 20001:
                id_20001_count += 1
                if self.last_header_size < 100 and id_20001_count >= 3:
                    return None

    def get_role_info(self, role_id, zone_id):
        try:
            self.send_data(10128, SdpStruct({1: int(role_id), 2: int(zone_id)}))
            best_res = None
            for _ in range(30):
                pid, res = self.recv_data()
                if pid is None or pid == -1:
                    break
                elif pid == 20001:
                    continue
                elif pid == 10129:
                    if res is None:
                        continue
                    if best_res is None:
                        best_res = res
                    try:
                        if int(res.get(9, 0) or 0) > 0:
                            return res
                    except (TypeError, ValueError):
                        pass
                    continue
            return best_res
        except Exception:
            return None

    def get_skin_role_info(self, role_id, zone_id, max_retries=3):
        for _ in range(max_retries):
            try:
                self.send_data(10143, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                while timeout_count < 3:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid == 10144:
                        return res
                    elif pid == 20001:
                        continue
            except Exception:
                pass
        return None

    def get_v2l_status(self, role_id, zone_id, max_retries=2):
        for _ in range(max_retries):
            try:
                self.send_data(10208, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                while timeout_count < 2:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid == 10208:
                        if res is not None:
                            return {"_source": 10208, "_data": dict(res)}
                    elif pid == 20001:
                        continue
                self.send_data(10145, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                while timeout_count < 2:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid in (10146, 10160):
                        if res is not None:
                            return {"_source": pid, "_data": dict(res)}
                    elif pid == 20001:
                        continue
            except Exception:
                pass
        return None

    def filter_by_server(self, result, target_server):
        if not result or not result.get(0):
            return None
        for player in result[0]:
            if isinstance(player, dict) and player.get(1) == target_server:
                return {0: [player]}
        return None

    def _banned_player_data(self, base_result=None, role_info=None, v2l_data=None):
        info = self.ban_info or {}
        player = None
        if base_result is not None:
            try:
                player = extract_player_data(
                    base_result, role_info=role_info,
                    creation_ts=self.creation_ts, v2l_data=v2l_data, ban_info=info,
                )
            except Exception:
                player = None
        if player is None:
            player = {
                "nickname": None, "level": 0,
                "current_rank": "Unknown", "high_rank": "Unknown",
                "skin_count": 0, "hero_count": 0,
                "collector_tier": "No Tier", "collector_point": 0,
                "skin_breakdown": {}, "hero_history": [],
                "last_heroes_purchase": [], "emblem_levels": [],
                "skin_history": [], "last_match": None,
            }
        player["ban_status"] = "BANNED"
        code = info.get("ban_code")
        reason = info.get("reason_name")
        if code or reason:
            player["ban_code"] = code or "21"
            player["ban_reason"] = reason or BAN_REASONS.get(
                player["ban_code"], "Using Plug-in Apps to Compromise Competitive Fairness")
        else:
            player["ban_code"] = None
            player["ban_reason"] = None
        player["ban_duration"] = format_ban_duration(info)
        return player

# ── SKIN PARSING ────────────────────────────────────────────────────
def parse_skin_counts(tag_118):
    if not tag_118 or not isinstance(tag_118, dict):
        return {}
    skin_data = None
    for k in (4, 0, 1):
        v = tag_118.get(k)
        if isinstance(v, dict) and v:
            skin_data = v
            break
    if skin_data is None:
        skin_data = tag_118
    if not isinstance(skin_data, dict):
        return {}
    skin_types = {6: "Supreme Skins", 5: "Grand Skins", 4: "Exquisite Skins",
                  3: "Deluxe Skins", 2: "Exceptional Skins", 1: "Common Skins"}
    skin_counts = {}
    for skin_id, count in skin_data.items():
        try:
            skin_id_int = int(skin_id)
        except (ValueError, TypeError):
            continue
        if skin_id_int in skin_types:
            skin_counts[skin_types[skin_id_int]] = count
    return skin_counts

# ── PLAYER DATA EXTRACTION ──────────────────────────────────────────
def extract_player_data(result, role_info=None, creation_ts=0, v2l_data=None, ban_info=None):
    if not result or not result.get(0):
        return None
    first = result[0]
    if isinstance(first, dict):
        player_data = first
    elif isinstance(first, list) and first and isinstance(first[0], dict):
        player_data = first[0]
    else:
        return None
    try:
        nickname = player_data.get(2, "Unknown")
        player_id = player_data.get(0, "Unknown")
        server = player_data.get(1, "Unknown")
        level = player_data.get(3, "Unknown")
        skin = player_data.get(83, "Unknown")
        hero_count = player_data.get(4, 0)
        matches = player_data.get(17, 0)
        rating_score = player_data.get(9, 0)
        if role_info:
            hero_count = role_info.get(9, hero_count) or hero_count
            matches = role_info.get(22, matches) or matches

        location = "NOT FOUND"
        location_data = player_data.get(71, None)
        if location_data and isinstance(location_data, list) and len(location_data) >= 2:
            location = ", ".join(location_data)

        last_login = player_data.get(5, 0)
        last_login_formatted = format_timestamp(last_login)
        last_login_country = player_data.get(87, "Unknown")
        create_account_country = player_data.get(97, "Unknown")
        squad_icon = player_data.get(31, "")
        squad_name = player_data.get(30, "").replace("`", "").strip()
        squad = f"{squad_icon} {squad_name}".strip() if squad_name else "—"
        squad_id = 0
        if role_info and isinstance(role_info, dict):
            squad_id = role_info.get(34, 0)
        if not squad_id:
            squad_id = player_data.get(34, player_data.get(28, 0))
        squad_id_display = f"Squad ID: {squad_id}" if squad_id else "N/A"

        tag_95 = player_data.get(95)
        tag_8 = player_data.get(8)
        high_rank = map_rank(tag_95) if tag_95 is not None else "Unknown"
        current_rank = map_rank(tag_8) if tag_8 is not None else "Unknown"
        achievement_points = player_data.get(7, 0)
        tag_136 = player_data.get(136, {})
        collector_point = tag_136.get(9, 0) if isinstance(tag_136, dict) else 0
        collector_rank = tag_136.get(10, 0) if isinstance(tag_136, dict) else 0
        collector_tier = map_collector_point(collector_point)
        tag_91 = player_data.get(91, [])
        hero_history = get_hero_history(tag_91) if tag_91 else ["Private / Not Available"]

        v2l_status = "N/A"
        if v2l_data and isinstance(v2l_data, dict):
            source = v2l_data.get("_source", 0)
            data = v2l_data.get("_data", {})
            tags = (10, 11) if source == 10208 else (0, 2, 3, 5)
            for _tag in tags:
                _v = data.get(_tag)
                if _v is not None:
                    try:
                        v2l_status = "Enabled" if int(_v) > 0 else "Disabled"
                        break
                    except (ValueError, TypeError):
                        pass

        followers = (role_info or {}).get(23, 0) or player_data.get(15, 0)
        popularity = player_data.get(14, 0)
        bio = player_data.get(24, "").strip() if isinstance(player_data.get(24), str) else ""
        likes = (role_info or {}).get(24, 0) or player_data.get(61, 0)

        credits_score = "N/A"
        _cs_val = (role_info or {}).get(20, 0)
        if isinstance(_cs_val, int) and _cs_val > 0:
            credits_score = f"{_cs_val}/110"
        else:
            _cs_fb = player_data.get(80, 0)
            if isinstance(_cs_fb, int) and _cs_fb > 0:
                credits_score = f"{_cs_fb}/110"

        restriction_flags = "None"
        _t117 = (role_info or {}).get(117) if role_info else None
        if _t117 is None:
            _t117 = player_data.get(117)
        if _t117 is not None:
            _raw = _t117.get(0, 0) if isinstance(_t117, dict) else _t117
            try:
                _flag_count = int(_raw) + 1
                _pct = round((_flag_count / 7) * 100, 1)
                if _pct < 30:
                    _risk, _icon = "Low Risk", "✅"
                elif _pct < 60:
                    _risk, _icon = "Medium Risk", "⚠️"
                else:
                    _risk, _icon = "High Risk", "🚨"
                restriction_flags = f"{_pct}% {_icon} ({_risk})"
            except Exception:
                pass

        _t135 = player_data.get(135, {})
        _aff_level = _t135.get(1, 0) if isinstance(_t135, dict) else 0
        _AFF = {0: "None", 1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum", 5: "Diamond"}
        _aff_tier = _AFF.get(_aff_level, f"Level {_aff_level}") if _aff_level else "None"
        _aff_names = []
        if role_info and isinstance(role_info, dict):
            _tag82 = role_info.get(82, [])
            if isinstance(_tag82, list):
                for _entry in _tag82:
                    if isinstance(_entry, dict):
                        _n = _entry.get(2, "")
                        if _n and isinstance(_n, str):
                            _aff_names.append(_n)
        affinity_label = ", ".join(_aff_names) if _aff_names else _aff_tier

        _skin_ts = player_data.get(176, 0) or (role_info or {}).get(176, 0)
        latest_skin_date = format_timestamp(_skin_ts) if isinstance(_skin_ts, int) and _skin_ts > 100000000 else "N/A"
        _latest_skin_id = player_data.get(175, 0) or (role_info or {}).get(175, 0)
        if _latest_skin_id:
            _tier_from_db = get_skin_tier(_latest_skin_id)
            latest_skin_tier = _tier_from_db or "Unknown"
            latest_skin_id_str = f"{_latest_skin_id} ({latest_skin_tier})"
        else:
            latest_skin_id_str = "N/A"
            latest_skin_tier = None

        _SL_TAGS = [21, 47, 50]
        _sl_expiry = 0
        for _sl_t in _SL_TAGS:
            if _sl_expiry:
                break
            if role_info and isinstance(role_info, dict):
                _v = role_info.get(_sl_t, 0) or 0
                if isinstance(_v, int) and _v > 1700000000:
                    _sl_expiry = _v
        for _sl_t in _SL_TAGS:
            if _sl_expiry:
                break
            _v = player_data.get(_sl_t, 0) or 0
            if isinstance(_v, int) and _v > 1700000000:
                _sl_expiry = _v
        if _sl_expiry:
            starlight_user = "Yes ⭐" if _sl_expiry > time.time() else "No"
        else:
            starlight_user = "No"

        starlight_months = player_data.get(60, 0)
        tickets = (role_info or {}).get(49, 0) or player_data.get(49, 0)
        total_wins = player_data.get(18, 0)

        _MIN_VALID_TS = 1451577600
        _create_ts_fallback = player_data.get(6, 0)
        if creation_ts and creation_ts >= _MIN_VALID_TS:
            creation_date = format_timestamp_full(creation_ts)
        elif _create_ts_fallback and _create_ts_fallback >= _MIN_VALID_TS:
            creation_date = format_timestamp_full(_create_ts_fallback)
        else:
            creation_date = "N/A"

        account_age = "N/A"
        _age_ts = creation_ts if (creation_ts and creation_ts >= _MIN_VALID_TS) else \
                  (_create_ts_fallback if (_create_ts_fallback and _create_ts_fallback >= _MIN_VALID_TS) else 0)
        if _age_ts:
            _now_utc = _dt.now(timezone.utc)
            _create_dt = _dt.fromtimestamp(_age_ts, timezone.utc)
            _age_delta = _now_utc - _create_dt
            _y = _age_delta.days // 365
            _m = (_age_delta.days % 365) // 30
            _d = _age_delta.days % 30
            if _y > 0:
                account_age = f"{_y}y {_m}m {_d}d"
            elif _m > 0:
                account_age = f"{_m}m {_d}d"
            else:
                account_age = f"{_age_delta.days}d"

        _tag45 = player_data.get(45, {}) or (role_info or {}).get(45, {})
        last_heroes_purchase = "N/A"
        if isinstance(_tag45, dict) and _tag45:
            _entries = []
            for _entry in _tag45.values():
                if isinstance(_entry, dict):
                    _hid = _entry.get(0, 0)
                    _hts = _entry.get(1, 0)
                    _entries.append((_hts, HERO_ID_MAP.get(_hid, f"Unknown({_hid})")))
            _entries.sort(key=lambda x: x[0], reverse=True)
            if _entries:
                last_heroes_purchase = ", ".join(h for _, h in _entries)

        mcl_wins = (role_info or {}).get(46, 0) or player_data.get(104, player_data.get(103, 0))

        win_count = (role_info or {}).get(22, 0)
        total_battles = (role_info or {}).get(77, 0) or player_data.get(17, 0)
        _wins_for_rate = win_count if win_count else total_wins
        if total_battles > 0 and _wins_for_rate > 0:
            _wr = (_wins_for_rate / total_battles) * 100
            win_rate = f"{min(_wr, 100):.1f}%"
        else:
            win_rate = "N/A"

        squad_motto = "N/A"
        if role_info and isinstance(role_info, dict):
            _motto = role_info.get(24, "")
            if _motto and isinstance(_motto, str):
                squad_motto = _motto

        diamonds = 0
        bp = 0
        if role_info and isinstance(role_info, dict):
            _cur = role_info.get(111, None)
            if isinstance(_cur, dict):
                diamonds = int(_cur.get(0, 0) or 0)
                bp       = int(_cur.get(1, 0) or 0)
            elif isinstance(_cur, int):
                diamonds = int(_cur or 0)
            elif isinstance(_cur, list) and _cur:
                diamonds = int(_cur[0] or 0) if len(_cur) > 0 else 0
                bp       = int(_cur[1] or 0) if len(_cur) > 1 else 0
        if not bp:
            bp = int(player_data.get(83, 0) or 0)

        skin_history = []
        if role_info and isinstance(role_info, dict):
            _tag92 = role_info.get(92, [])
            if isinstance(_tag92, list):
                for _entry in _tag92[:5]:
                    if isinstance(_entry, dict):
                        _sid = _entry.get(0, 0)
                        _tier = _entry.get(2, 0)
                        _ts = _entry.get(4, 0)
                        _tn = {1: "Common", 2: "Exceptional", 3: "Deluxe",
                               4: "Exquisite", 5: "Grand", 6: "Supreme"}.get(_tier, f"T{_tier}")
                        _d = format_timestamp(_ts) if _ts else "?"
                        skin_history.append(f"SkinID:{_sid}({_tn})|{_d}")
        skin_history_str = ", ".join(skin_history) if skin_history else "N/A"

        _EMBLEM_MAP = {1: "Fighter", 2: "Assassin", 3: "Mage", 4: "Marksman",
                       5: "Support", 6: "Tank", 7: "Common"}
        emblem_levels = "N/A"
        if role_info and isinstance(role_info, dict):
            _tag101 = role_info.get(101, {})
            if isinstance(_tag101, dict) and _tag101:
                _parts = [f"{_EMBLEM_MAP.get(eid, f'E{eid}')}:Lv{_tag101[eid]}"
                          for eid in sorted(_tag101.keys())]
                emblem_levels = ", ".join(_parts) if _parts else "N/A"

        skin_counts = {"Supreme Skins": 0, "Grand Skins": 0, "Exquisite Skins": 0,
                       "Deluxe Skins": 0, "Exceptional Skins": 0, "Common Skins": 0}
        _tag118 = (role_info or {}).get(118) or player_data.get(118)
        if _tag118:
            _parsed = parse_skin_counts(_tag118)
            if _parsed:
                skin_counts.update(_parsed)

        # ban sniff
        ban_detected, detected_info = inspect_ban(result)
        if not ban_detected and role_info:
            b2, i2 = inspect_ban(role_info)
            if b2:
                ban_detected, detected_info = True, i2
        if ban_info and isinstance(ban_info, dict) and ban_info:
            day = ban_info.get("endtime_day")
            try:
                d = int(day) if day is not None else None
            except (TypeError, ValueError):
                d = None
            has_signal = (
                (d is not None and d > 0) or
                (d is not None and d > 1_000_000_000) or
                str(ban_info.get("ban_status_raw", "")).strip().lower()
                in ("1", "true", "yes", "banned", "ban")
            )
            if has_signal:
                ban_detected = True
                merged = dict(detected_info)
                merged.update(ban_info)
                detected_info = merged

        if ban_detected and not detected_info.get("reason_name"):
            code = detected_info.get("ban_code") or "21"
            detected_info["ban_code"] = code
            detected_info["reason_name"] = BAN_REASONS.get(
                code, "Using Plug-in Apps to Compromise Competitive Fairness")

        bindings_str = extract_bindings(player_data)

        return {
            "nickname": nickname, "player_id": player_id, "server": server,
            "level": level, "skin_count": skin, "hero_count": hero_count,
            "matches": matches, "rating_score": rating_score, "location": location,
            "last_login": last_login_formatted, "last_login_country": last_login_country,
            "create_account_country": create_account_country,
            "high_rank": high_rank, "current_rank": current_rank,
            "achievement_points": achievement_points,
            "collector_point": collector_point, "collector_rank": collector_rank,
            "collector_tier": collector_tier, "hero_history": hero_history,
            "squad": squad, "squad_id": squad_id_display, "skin_breakdown": skin_counts,
            "affinity": affinity_label, "likes": likes,
            "credits_score": credits_score if credits_score != "N/A" else None,
            "followers": followers, "popularity": popularity,
            "bio": bio if bio else None,
            "latest_skin_date": latest_skin_date,
            "latest_skin_tier": latest_skin_tier,
            "starlight_user": starlight_user, "starlight_months": starlight_months or None,
            "tickets": tickets or None, "total_wins": total_wins or None,
            "restriction_flags": restriction_flags,
            "last_heroes_purchase": last_heroes_purchase,
            "mcl_champion_wins": mcl_wins, "v2l_status": v2l_status,
            "creation_date": creation_date, "account_age": account_age,
            "win_count": win_count, "total_battles": total_battles,
            "win_rate": win_rate, "battle_points": bp or None,
            "diamonds": diamonds or None, "squad_motto": squad_motto if squad_motto != "N/A" else None,
            "skin_history": skin_history_str if skin_history_str != "N/A" else None,
            "emblem_levels": emblem_levels if emblem_levels != "N/A" else None,
            "latest_skin_id": latest_skin_id_str if latest_skin_id_str != "N/A" else None,
            "bindings": bindings_str,
            "ban_status": "BANNED" if ban_detected else "CLEAN",
            "ban_code": detected_info.get("ban_code") if ban_detected else None,
            "ban_reason": detected_info.get("reason_name") if ban_detected else None,
            "ban_duration": format_ban_duration(detected_info) if ban_detected else None,
        }
    except Exception:
        logger.exception("extract_player_data failed")
        return None

# ── MAIN LOOKUP ENTRY (10 retries: login -> fetch account info) ─────
def lookup_player_data(player_id_or_nickname, server_id=None, guid=None,
                       session=None, combo_v2l=None):
    """
    Performs up to MAX_LOOKUP_RETRIES (10) full attempts. Each attempt:
      1. opens a fresh GameConnection (login + game-server selection)
      2. connects to the game server
      3. fetches the player profile + role info + v2l status
      4. extracts and returns the parsed profile

    Any failure in steps 1-4 consumes one attempt and triggers a retry.
    Returns success only when a full player_data dict has been built.
    """
    try:
        try:
            player_id = int(player_id_or_nickname)
            search_type = "id"
            search_value = player_id
            server_filter = None
        except ValueError:
            search_type = "nickname"
            search_value = str(player_id_or_nickname).strip()
            if not server_id:
                return {"error": "Server ID is required when searching by nickname",
                        "status": "error"}
            try:
                server_filter = int(server_id)
            except ValueError:
                return {"error": "Server ID must be a number", "status": "error"}

        if not load_device_ids():
            return {"error": "No device IDs available", "status": "error"}

        retry_count = 0
        last_error = None

        while retry_count < MAX_LOOKUP_RETRIES:
            retry_count += 1
            logger.info("lookup attempt %d/%d for %s",
                        retry_count, MAX_LOOKUP_RETRIES, search_value)

            device_ids = load_device_ids()
            device_models = load_device_models()
            current_device_id = random.choice(device_ids)
            current_device_model = random.choice(device_models) if device_models else None

            conn = None
            try:
                conn = GameConnection(device_id=current_device_id,
                                      device_model=current_device_model)
                conn.__enter__()  # connect to login server

                # ── Step 1: login ──
                ok, _ = conn.login()
                if not ok:
                    last_error = "LOGIN_FAILED"
                    raise ConnectionError("LOGIN_FAILED")

                if conn.ban_seen:
                    logger.info("ban detected during login (attempt %d)", retry_count)
                    return {"status": "success",
                            "player_data": conn._banned_player_data(None, None, None)}

                # ── Step 2: get game server ──
                ok, _ = conn.get_server()
                if not ok:
                    last_error = "NO_GAME_SERVER"
                    raise ConnectionError("NO_GAME_SERVER")

                if conn.ban_seen:
                    return {"status": "success",
                            "player_data": conn._banned_player_data(None, None, None)}

                # ── Step 3: enter game server + handshake ──
                conn.enter_game()

                if not conn.handshake():
                    if conn.ban_seen:
                        return {"status": "success",
                                "player_data": conn._banned_player_data(None, None, None)}
                    last_error = "HANDSHAKE_FAILED"
                    raise ConnectionError("HANDSHAKE_FAILED")

                if conn.ban_seen:
                    return {"status": "success",
                            "player_data": conn._banned_player_data(None, None, None)}

                # ── Step 4: lookup player ──
                if search_type == "id":
                    result = conn.lookup_player(search_value, "id")
                else:
                    result = conn.lookup_player(search_value, "nickname", server_filter)

                _creation_ts = conn.creation_ts

                if conn.ban_seen:
                    return {"status": "success",
                            "player_data": conn._banned_player_data(result, None, None)}

                if result is None:
                    last_error = "LOOKUP_EMPTY"
                    raise ConnectionError("LOOKUP_EMPTY")

                _res_role_id = result[0][0].get(0, search_value) if (result and result[0]) else search_value
                _res_zone_id = result[0][0].get(1, 0) if (result and result[0]) else 0

                # ── Step 5: fetch skin + full role info ──
                role_info_data = None
                try:
                    skin_role_info = conn.get_skin_role_info(_res_role_id, _res_zone_id)
                    if skin_role_info and isinstance(skin_role_info, dict):
                        role_info_data = dict(skin_role_info)
                except Exception as e:
                    last_error = f"Skin role info failed: {e}"

                try:
                    full_role_info = conn.get_role_info(_res_role_id, _res_zone_id)
                    if full_role_info and isinstance(full_role_info, dict):
                        if role_info_data is None:
                            role_info_data = {}
                        for _k, _v in full_role_info.items():
                            if _k not in role_info_data or not role_info_data[_k]:
                                role_info_data[_k] = _v
                except Exception:
                    pass

                if conn.ban_seen:
                    return {"status": "success",
                            "player_data": conn._banned_player_data(
                                result, role_info_data, None)}

                # ── Step 6: V2L status ──
                _v2l_data = None
                try:
                    _v2l_data = conn.get_v2l_status(_res_role_id, _res_zone_id)
                except Exception:
                    pass

                if conn.ban_seen:
                    return {"status": "success",
                            "player_data": conn._banned_player_data(
                                result, role_info_data, _v2l_data)}

                # ── Step 7: extract + validate ──
                _ban_seen, _ban_info = inspect_ban(result)
                if not _ban_seen and role_info_data:
                    _b2, _i2 = inspect_ban(role_info_data)
                    if _b2:
                        _ban_seen, _ban_info = True, _i2

                player_data = extract_player_data(
                    result, role_info=role_info_data, creation_ts=_creation_ts,
                    v2l_data=_v2l_data,
                    ban_info=(_ban_info if _ban_seen else None),
                )

                if player_data is None:
                    last_error = "EXTRACT_FAILED"
                    raise ConnectionError("EXTRACT_FAILED")

                if player_data.get("v2l_status", "N/A") == "N/A" and combo_v2l:
                    player_data["v2l_status"] = combo_v2l

                logger.info("lookup succeeded on attempt %d/%d",
                            retry_count, MAX_LOOKUP_RETRIES)
                return {"status": "success", "player_data": player_data}

            except ConnectionError as e:
                error_msg = str(e)
                last_error = f"Connection error: {error_msg}"
                logger.warning("attempt %d failed: %s", retry_count, last_error)
                if "LOGIN_FAILED" in error_msg:
                    remove_failed_device_id(current_device_id)
            except socket.timeout as e:
                last_error = f"Socket timeout: {e}"
                logger.warning("attempt %d timeout: %s", retry_count, last_error)
            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__}: {e}"
                logger.warning("attempt %d unexpected: %s", retry_count, last_error)
            finally:
                if conn is not None:
                    try:
                        conn.cleanup()
                    except Exception:
                        pass

            # brief backoff between retries (1s..5s)
            if retry_count < MAX_LOOKUP_RETRIES:
                time.sleep(min(retry_count, 5))

        logger.error("lookup failed after %d attempts: %s",
                     MAX_LOOKUP_RETRIES, last_error)
        return {"error": last_error or f"Player not found after {MAX_LOOKUP_RETRIES} retries",
                "status": "error"}

    except Exception as e:
        logger.exception("critical lookup failure")
        return {"error": f"Critical error: {type(e).__name__}: {e}", "status": "error"}

# ═════════════════════════════════════════════════════════════════════
#  TELEGRAM BOT LAYER
# ═════════════════════════════════════════════════════════════════════

# ── EMOJI HELPERS ────────────────────────────────────────────────────
def CE(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

E_CHECK     = CE("6147565374289220368", "✅")
E_CROSS     = CE("5215204871422093648", "❌")
E_USER      = CE("5346136537123801643", "👤")
E_KEY       = CE("6077967323338120655", "🔑")
E_LOCK      = CE("5807952667992920776", "🔐")
E_MONEY     = CE("6334490648887958653", "💰")
E_ANNOUNCE  = CE("5836698068061261980", "📢")
E_CLOCK     = CE("5305251768475592088", "🕒")
E_HOURGLASS = CE("5212985021870123409", "⏳")
E_CROWN     = CE("5217822164362739968", "👑")
E_WAVE      = CE("6122769630441247863", "👋")
E_SEP       = CE("5465629669829128119", "➿") * 10

RANK_EMOJI = {
    "warrior": "🥉", "elite": "🥈", "master": "🎖️", "grandmaster": "🏵️",
    "epic": "💠", "legend": "🔷", "mythic": "🔮", "mythical glory": "👑",
    "mythical honor": "⚡", "mythical immortal": "🌟",
}

def _rank_icon(rank):
    if not rank:
        return "▪️"
    for k, v in RANK_EMOJI.items():
        if k in str(rank).strip().lower():
            return v
    return "▪️"

# ── DATABASE ─────────────────────────────────────────────────────────
def init_db():
    db_dir = os.path.dirname(os.path.abspath(DB_FILE))
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_admin INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_expiry INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            lookup_count INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            duration INTEGER,
            used_by INTEGER,
            created_at INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            user_id INTEGER NOT NULL,
            day_key TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, day_key)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── DAILY LIMIT HELPERS ──────────────────────────────────────────────
def _today_key() -> str:
    return _dt.now(DAILY_RESET_TZ).strftime("%Y-%m-%d")

def _seconds_until_reset() -> int:
    now = _dt.now(DAILY_RESET_TZ)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return max(0, int((tomorrow - now).total_seconds()))

def get_daily_count(user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT count FROM daily_usage WHERE user_id = ? AND day_key = ?",
              (user_id, _today_key()))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0

def increment_daily_count(user_id: int) -> int:
    key = _today_key()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO daily_usage (user_id, day_key, count) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, day_key) DO UPDATE SET count = count + 1",
        (user_id, key),
    )
    conn.commit()
    c.execute("SELECT count FROM daily_usage WHERE user_id = ? AND day_key = ?",
              (user_id, key))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 1

def daily_remaining(user_id: int, is_premium_user: bool, is_admin_user: bool) -> Optional[int]:
    if is_admin_user or is_premium_user:
        return None
    return max(0, DAILY_FREE_LIMIT - get_daily_count(user_id))

# ── USER HELPERS ─────────────────────────────────────────────────────
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0], "username": row[1],
            "is_admin": bool(row[2]), "is_premium": bool(row[3]),
            "premium_expiry": row[4], "banned": bool(row[5]),
            "lookup_count": row[6],
        }
    return None

def create_or_update_user(user_id: int, username: str = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    existing = get_user(user_id)
    if not existing:
        is_admin_val = 1 if user_id in ADMIN_IDS else 0
        c.execute("INSERT INTO users (user_id, username, is_admin) VALUES (?, ?, ?)",
                  (user_id, username, is_admin_val))
    elif username:
        c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

def increment_lookup(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if get_user(user_id) is None:
        create_or_update_user(user_id)
    c.execute("UPDATE users SET lookup_count = lookup_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id: int) -> bool:
    u = get_user(user_id)
    return u["banned"] if u else False

def is_premium(user_id: int) -> bool:
    u = get_user(user_id)
    if not u:
        return False
    if u["is_premium"]:
        if u["premium_expiry"] == 0 or time.time() < u["premium_expiry"]:
            return True
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET is_premium = 0, premium_expiry = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    return False

def is_admin(user_id: int) -> bool:
    u = get_user(user_id)
    return u["is_admin"] if u else False

def ban_user(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def generate_key(duration_seconds: int) -> str:
    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO keys (key, duration, created_at) VALUES (?, ?, ?)",
              (key, duration_seconds, int(time.time())))
    conn.commit()
    conn.close()
    return key

def redeem_key(user_id: int, key: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT duration, used_by FROM keys WHERE key = ?", (key,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    duration, used_by = row
    if used_by is not None:
        conn.close()
        return False
    c.execute("UPDATE keys SET used_by = ? WHERE key = ?", (user_id, key))
    if duration == 0:
        expiry, is_prem = 0, 1
    else:
        expiry, is_prem = int(time.time()) + duration, 1
    c.execute("UPDATE users SET is_premium = ?, premium_expiry = ? WHERE user_id = ?",
              (is_prem, expiry, user_id))
    conn.commit()
    conn.close()
    return True

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, is_admin, is_premium, banned, lookup_count "
              "FROM users ORDER BY lookup_count DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_top_users(limit=10):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, lookup_count FROM users "
              "ORDER BY lookup_count DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def is_allowed_chat(chat) -> bool:
    return chat.id == CHANNEL_ID or chat.type == "private"

# ── ASYNC LOOKUP BRIDGE ─────────────────────────────────────────────
_LOOKUP_EXECUTOR = None

async def run_lookup(role_id, zone_id, retries: int = 1) -> Dict[str, Any]:
    """
    Run the synchronous lookup in an executor.
    The sync lookup_player_data already performs up to 10 full retries,
    so this wrapper only retries on catastrophic executor failures.
    """
    loop = asyncio.get_running_loop()

    def _sync():
        return lookup_player_data(str(role_id), server_id=zone_id)

    last_err = None
    for attempt in range(retries):
        try:
            result = await loop.run_in_executor(_LOOKUP_EXECUTOR, _sync)
            if result.get("status") == "success":
                return result
            last_err = result.get("error", "Unknown error")
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            logger.exception("executor lookup attempt %d failed", attempt + 1)
        if attempt < retries - 1:
            await asyncio.sleep(2 ** attempt)
    return {"status": "error", "error": last_err or "Lookup failed after retries"}

# ── LOADING ANIMATION ────────────────────────────────────────────────
LOADING_FRAMES = [
    ("🛰️", "Connecting to login server", 15),
    ("📡", "Fetching game server", 30),
    ("🔐", "Handshaking account", 50),
    ("🧬", "Parsing player profile", 70),
    ("🃏", "Loading hero & skin data", 85),
    ("✨", "Finalizing report", 97),
]

def _progress_bar(pct: int, width: int = 12) -> str:
    filled = round(width * pct / 100)
    return "▰" * filled + "▱" * (width - filled)

def _loading_text(role_id, zone_id, icon, label, pct):
    return (
        f"<b>{icon} Looking Up Account</b>\n"
        f"<code>{role_id}:{zone_id}</code>\n\n"
        f"{_progress_bar(pct)}  <b>{pct}%</b>\n"
        f"<i>{label}…</i>"
    )

async def _animate_search(message, role_id, zone_id):
    try:
        while True:
            for icon, label, pct in LOADING_FRAMES:
                try:
                    await message.edit_text(
                        _loading_text(role_id, zone_id, icon, label, pct),
                        parse_mode="HTML",
                    )
                except Exception:
                    # message may have been deleted or edit failed — silently skip
                    pass
                await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug("animation loop ended: %s", e)

# ── FORMAT OUTPUT ────────────────────────────────────────────────────
def format_result(role_id, zone_id, player_data: dict) -> str:
    d = player_data or {}
    SEP = "─" * 20

    def g(k, default="—"):
        v = d.get(k, default)
        return default if v is None or v == "" else v

    nick        = g("nickname")
    level       = g("level")
    cur_rank    = g("current_rank")
    high_rank   = g("high_rank")
    hero_count  = g("hero_count", 0)
    skin_count  = g("skin_count", 0)
    breakdown   = d.get("skin_breakdown") or {}
    c_point     = d.get("collector_point", 0)
    c_tier      = g("collector_tier")
    ach_pts     = d.get("achievement_points", 0)
    squad       = g("squad")
    location    = g("location")
    last_login  = g("last_login")
    bindings    = g("bindings")
    region      = g("create_account_country")
    hero_hist   = d.get("hero_history") or []
    matches     = d.get("total_battles") or d.get("matches")
    win_rate    = g("win_rate")
    wr_count    = d.get("win_count")
    latest_skin = g("latest_skin_id")
    latest_tier = g("latest_skin_tier")
    latest_date = g("latest_skin_date")
    starlight   = g("starlight_user")
    restriction = g("restriction_flags")
    ban_status  = g("ban_status")
    ban_reason  = d.get("ban_reason")
    ban_dur     = d.get("ban_duration")
    ban_code    = d.get("ban_code")
    creation    = g("creation_date")
    age         = g("account_age")
    diamonds    = d.get("diamonds") or 0
    bp          = d.get("battle_points") or 0
    tickets     = d.get("tickets") or 0
    emblem      = g("emblem_levels")
    skin_hist   = g("skin_history")

    lines = []
    lines.append("╔══════════════════════════╗")
    lines.append("║     MLBB ACCOUNT REPORT     ║")
    lines.append("╚══════════════════════════╝")
    lines.append("")

    lines.append("┌─ ACCOUNT")
    lines.append(f"  Role ID:        {role_id}")
    lines.append(f"  Zone ID:        {zone_id}")
    lines.append(f"  Nickname:       {nick}")
    lines.append(f"  Level:          {level}")
    lines.append(f"  Region:         {region}")
    lines.append(f"  Created:        {creation}")
    lines.append(f"  Account Age:    {age}")
    lines.append(f"  Last Login:     {last_login}")
    lines.append(f"  Location:       {location}")
    lines.append(f"  Bindings:       {bindings}")

    is_banned = str(ban_status).upper() == "BANNED"
    if is_banned:
        lines.append("")
        lines.append("┌─ 🚫 ACCOUNT IS BANNED")
        if ban_reason:
            lines.append(f"  Reason:         {ban_reason}")
        if ban_code:
            lines.append(f"  Ban Code:       {ban_code}")
        if ban_dur:
            lines.append(f"  Duration:       {ban_dur}")
        lines.append("├" + SEP)
    else:
        lines.append(f"  Ban Status:     {ban_status}")
        lines.append("├" + SEP)

    lines.append("RANKS")
    lines.append(f"  Current:        {_rank_icon(cur_rank)} {cur_rank}")
    lines.append(f"  Highest:        {_rank_icon(high_rank)} {high_rank}")
    lines.append("├" + SEP)

    lines.append("COLLECTION")
    lines.append(f"  Heroes Owned:   {hero_count}")
    lines.append(f"  Total Skins:    {skin_count}")
    order = ["Supreme Skins", "Grand Skins", "Exquisite Skins",
             "Deluxe Skins", "Exceptional Skins", "Common Skins"]
    for rarity in order:
        if breakdown.get(rarity):
            lines.append(f"    └─ {rarity:<20} {breakdown[rarity]}")
    if c_point:
        lines.append(f"  Collector Pts:  {c_point:,}")
    if c_tier and c_tier != "—":
        lines.append(f"  Collector Tier: {c_tier}")
    if ach_pts:
        lines.append(f"  Achievement:    {ach_pts:,}")
    if latest_skin and latest_skin != "—":
        lines.append(f"  Latest Skin:    {latest_skin}")
        if latest_tier and latest_tier != "—":
            lines.append(f"    └─ Tier:      {latest_tier}")
        if latest_date and latest_date != "—":
            lines.append(f"    └─ Bought:    {latest_date}")
    lines.append("├" + SEP)

    lines.append("PERFORMANCE")
    if matches:
        lines.append(f"  Matches:        {matches}")
    if win_rate and win_rate != "—":
        extra = f" ({wr_count} wins)" if wr_count else ""
        lines.append(f"  Win Rate:       {win_rate}{extra}")
    if emblem and emblem != "—":
        lines.append(f"  Emblems:        {emblem}")
    lines.append("├" + SEP)

    if diamonds or bp or tickets:
        lines.append("  CURRENCY")
        if diamonds:
            lines.append(f"  Diamonds:       {diamonds:,}")
        if bp:
            lines.append(f"  Battle Points:  {bp:,}")
        if tickets:
            lines.append(f"  Tickets:        {tickets:,}")
        lines.append("├" + SEP)

    lines.append("MISC")
    lines.append(f"  Squad:          {squad}")
    lines.append(f"  Starlight:      {starlight}")
    lines.append(f"  Restriction:    {restriction}")
    if hero_hist:
        hist = ", ".join(str(h) for h in hero_hist[:6])
        lines.append(f"  Hero History:   {hist}")
    if skin_hist and skin_hist != "—":
        lines.append(f"  Recent Skins:   {skin_hist[:80]}")
    return "\n".join(lines)

# ── CORE LOOKUP FLOW ─────────────────────────────────────────────────
async def process_lookup(user_id, role_id, zone_id, update: Update,
                         context: ContextTypes.DEFAULT_TYPE,
                         consume_daily: bool = True):
    create_or_update_user(user_id, update.effective_user.username)
    if consume_daily and not (is_admin(user_id) or is_premium(user_id)):
        used = increment_daily_count(user_id)
        logger.info("user %s daily usage -> %s/%s", user_id, used, DAILY_FREE_LIMIT)

    status_msg = await update.message.reply_text(
        _loading_text(role_id, zone_id, *LOADING_FRAMES[0][:2], LOADING_FRAMES[0][2]),
        parse_mode="HTML",
    )
    anim_task = asyncio.create_task(_animate_search(status_msg, role_id, zone_id))
    try:
        data = await run_lookup(role_id, zone_id, retries=1)
    except Exception as e:
        anim_task.cancel()
        try:
            await status_msg.edit_text(
                f"⚠️ <b>Error:</b> <code>{html.escape(str(e)[:300])}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return
    anim_task.cancel()

    if data.get("status") == "success":
        player_data = data.get("player_data", {})
        try:
            await status_msg.edit_text(
                f"<b>{E_CHECK} Account Found</b>\n<code>{role_id}:{zone_id}</code>\n\n"
                f"{_progress_bar(100)}  <b>100%</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await asyncio.sleep(0.4)
        msg = format_result(role_id, zone_id, player_data)
        try:
            await status_msg.edit_text(f"<pre>{html.escape(msg)}</pre>", parse_mode="HTML")
        except Exception:
            await update.message.reply_text(msg)
            try:
                await status_msg.delete()
            except Exception:
                pass
        increment_lookup(user_id)
    else:
        err = data.get("error", "Account not found")
        try:
            await status_msg.edit_text(
                f"{E_CROSS} <b>Lookup failed</b>\n<code>{role_id}:{zone_id}</code>\n"
                f"<i>{html.escape(err[:300])}</i>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        async def delete_later():
            await asyncio.sleep(15)
            try:
                await status_msg.delete()
            except Exception:
                pass
        asyncio.create_task(delete_later())

# ── QUEUE ────────────────────────────────────────────────────────────
lookup_queue: asyncio.Queue = asyncio.Queue()

async def queue_worker():
    logger.info("queue worker started")
    while True:
        try:
            item = await lookup_queue.get()
            try:
                await process_lookup(
                    item["user_id"], item["role_id"], item["zone_id"],
                    item["update"], item["context"],
                    consume_daily=item.get("consume_daily", True),
                )
            except Exception as e:
                logger.exception("queue item failed: %s", e)
                try:
                    await item["update"].message.reply_text(
                        f"{E_CROSS} Lookup crashed: {html.escape(str(e)[:300])}",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            finally:
                lookup_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("queue worker error: %s", e)

# ── HANDLERS ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    user = update.effective_user
    create_or_update_user(user.id, user.username)

    unlimited = is_admin(user.id) or is_premium(user.id)
    if unlimited:
        limit_line = "💎 <b>Unlimited lookups</b> (premium/admin)"
    else:
        used = get_daily_count(user.id)
        left = max(0, DAILY_FREE_LIMIT - used)
        limit_line = (
            f"{E_CLOCK} <b>Daily limit:</b> {used}/{DAILY_FREE_LIMIT} used "
            f"({left} left today)\n"
            f"💎 Get a key to unlock unlimited — {OWNER_USERNAME}"
        )

    text = (
        f"{E_WAVE} <b>Welcome, {html.escape(user.first_name)}!</b>\n"
        f"{E_SEP}\n\n"
        f"🔍 <b>/lookup</b> role_id:zone_id\n"
        f"   Example: <code>/lookup 12345:67890</code>\n"
        f"   Or: <code>/lookup 12345 67890</code>\n"
        f"   Nickname: <code>/lookup SomeName 67890</code>\n\n"
        f"{limit_line}\n\n"
        f"{E_KEY} /redeem &lt;key&gt; — activate a premium key\n"
        f"🏆 /rankings — top lookup users\n"
        + (f"🔧 /admin — admin panel\n" if is_admin(user.id) else "")
        + f"\n{E_SEP}"
    )
    msg = await update.message.reply_text(text, parse_mode="HTML")
    async def delete_later():
        await asyncio.sleep(30)
        try:
            await msg.delete()
        except Exception:
            pass
    asyncio.create_task(delete_later())

# ── INPUT PARSER ─────────────────────────────────────────────────────
def parse_lookup_args(args) -> Tuple[Optional[Any], Optional[int], Optional[str]]:
    if not args:
        return None, None, (
            "Usage:\n"
            "/lookup role_id:zone_id\n"
            "/lookup role_id zone_id\n"
            "/lookup nickname zone_id\n\n"
            "Examples:\n"
            "/lookup 12345:67890\n"
            "/lookup 12345 67890\n"
            "/lookup SomeName 67890"
        )

    if len(args) == 2:
        first, second = args[0].strip(), args[1].strip()
        if not first and not second:
            return None, None, "Both arguments are empty."
        if not second.isdigit():
            return None, None, "Zone ID must be a number."
        zone_id = int(second)
        if first == "":
            return None, zone_id, (
                "Zone-only lookup is not supported by the game server.\n"
                "The MLBB protocol needs a <b>role_id</b> or a <b>nickname</b>.\n\n"
                "Try:\n"
                "• <code>/lookup 12345 " + str(zone_id) + "</code>\n"
                "• <code>/lookup SomeName " + str(zone_id) + "</code>"
            )
        if first.isdigit():
            return int(first), zone_id, None
        return first, zone_id, None

    if len(args) == 1:
        raw = args[0].strip()
        if not raw:
            return None, None, "Empty argument."
        if raw.startswith(":"):
            zone_str = raw[1:].strip()
            if not zone_str.isdigit():
                return None, None, "Zone ID after ':' must be a number."
            return None, int(zone_str), (
                "Zone-only lookup is not supported by the game server.\n"
                "You must also provide a <b>role_id</b> or a <b>nickname</b>.\n\n"
                "Try:\n"
                "• <code>/lookup 12345 " + zone_str + "</code>\n"
                "• <code>/lookup SomeName " + zone_str + "</code>"
            )
        if ":" in raw:
            parts = raw.split(":")
            if len(parts) != 2:
                return None, None, "Invalid format. Use role_id:zone_id"
            rid_s, zid_s = parts[0].strip(), parts[1].strip()
            if not zid_s.isdigit():
                return None, None, "Zone ID must be a number."
            zone_id = int(zid_s)
            if not rid_s:
                return None, zone_id, (
                    "Zone-only lookup is not supported by the game server.\n"
                    "You must also provide a <b>role_id</b> or a <b>nickname</b>.\n\n"
                    "Try:\n"
                    "• <code>/lookup 12345 " + zid_s + "</code>\n"
                    "• <code>/lookup SomeName " + zid_s + "</code>"
                )
            if rid_s.isdigit():
                return int(rid_s), zone_id, None
            return rid_s, zone_id, None
        if raw.isdigit():
            return int(raw), None, None
        return None, None, (
            "Nickname lookup requires a zone ID.\n"
            "Try: <code>/lookup " + html.escape(raw) + " 67890</code>"
        )

    return None, None, "Too many arguments. Use: /lookup role_id:zone_id"

def _format_reset_seconds(secs: int) -> str:
    if secs <= 0:
        return "now"
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"

async def lookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    user_id = update.effective_user.id
    create_or_update_user(user_id, update.effective_user.username)

    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return

    role_id, zone_id, err = parse_lookup_args(context.args)
    if err:
        await update.message.reply_text(err, parse_mode="HTML")
        return

    if role_id is None:
        await update.message.reply_text(
            f"{E_CROSS} A <b>role_id</b> or <b>nickname</b> is required.\n"
            f"Zone ID alone is not enough for the game server.\n\n"
            f"Try:\n"
            f"• <code>/lookup 12345 {zone_id}</code>\n"
            f"• <code>/lookup SomeName {zone_id}</code>",
            parse_mode="HTML",
        )
        return

    if not (is_admin(user_id) or is_premium(user_id)):
        used = get_daily_count(user_id)
        if used >= DAILY_FREE_LIMIT:
            secs = _seconds_until_reset()
            await update.message.reply_text(
                f"{E_CLOCK} <b>Daily limit reached</b>\n\n"
                f"You've used <b>{used}/{DAILY_FREE_LIMIT}</b> free lookups today.\n"
                f"Resets in <b>{_format_reset_seconds(secs)}</b> (UTC midnight).\n\n"
                f"💎 Unlock <b>unlimited</b> lookups with a key — {OWNER_USERNAME}\n"
                f"{E_KEY} Redeem: <code>/redeem &lt;key&gt;</code>",
                parse_mode="HTML",
            )
            return

    if is_admin(user_id) or is_premium(user_id):
        await process_lookup(user_id, role_id, zone_id, update, context,
                             consume_daily=False)
        return

    await lookup_queue.put({
        "user_id": user_id, "role_id": role_id, "zone_id": zone_id,
        "update": update, "context": context, "consume_daily": True,
    })
    qsize = lookup_queue.qsize()
    dots = "🟠" * min(qsize, 5) + "⚪" * max(0, 5 - qsize)
    remaining = max(0, DAILY_FREE_LIMIT - get_daily_count(user_id) - 1)
    queue_msg = await update.message.reply_text(
        f"{E_HOURGLASS} <b>Queued</b>\n"
        f"<code>{role_id}:{zone_id}</code>\n\n"
        f"{dots}\n"
        f"Position: <b>{qsize}</b>\n"
        f"{E_CLOCK} Free lookups left today: <b>{remaining}</b>/{DAILY_FREE_LIMIT}\n\n"
        f"💎 Skip the queue + unlimited lookups — {OWNER_USERNAME}\n"
        f"Use /redeem <code>&lt;key&gt;</code> to activate {E_KEY}",
        parse_mode="HTML",
    )
    async def delete_later():
        await asyncio.sleep(15)
        try:
            await queue_msg.delete()
        except Exception:
            pass
    asyncio.create_task(delete_later())

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /redeem <key>\n\nTo buy a premium key, contact: " + OWNER_USERNAME,
            parse_mode="HTML",
        )
        return
    ok = redeem_key(user_id, args[0])
    if ok:
        await update.message.reply_text(
            f"{E_CHECK} <b>Premium activated!</b> You can now skip the queue "
            f"and have unlimited daily lookups. {E_KEY}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"{E_CROSS} <b>Invalid or already used key.</b>\n\nContact {OWNER_USERNAME} to get one.",
            parse_mode="HTML",
        )

async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    user_id = update.effective_user.id
    create_or_update_user(user_id, update.effective_user.username)

    if is_admin(user_id) or is_premium(user_id):
        await update.message.reply_text(
            "💎 <b>Unlimited</b> lookups — you are premium/admin.",
            parse_mode="HTML",
        )
        return

    used = get_daily_count(user_id)
    left = max(0, DAILY_FREE_LIMIT - used)
    secs = _seconds_until_reset()
    bar_w = 10
    filled = round(bar_w * used / DAILY_FREE_LIMIT)
    bar = "▰" * filled + "▱" * (bar_w - filled)

    await update.message.reply_text(
        f"{E_CLOCK} <b>Daily usage</b>\n\n"
        f"{bar}  <b>{used}/{DAILY_FREE_LIMIT}</b>\n"
        f"Remaining today: <b>{left}</b>\n"
        f"Resets in: <b>{_format_reset_seconds(secs)}</b> (UTC midnight)\n\n"
        f"💎 Unlimited with a premium key — {OWNER_USERNAME}",
        parse_mode="HTML",
    )

async def rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    users = get_top_users(10)
    if not users:
        await update.message.reply_text("No users yet.")
        return
    lines = [f"🏆 <b>Top Lookup Users</b>\n{E_SEP}"]
    for idx, (uid, uname, count) in enumerate(users, 1):
        uname = uname or f"User {uid}"
        crown = E_CROWN if uid in ADMIN_IDS else ""
        lines.append(f"{idx}. {crown}<b>{html.escape(str(uname))}</b> — {count} lookups")
    lines.append(E_SEP)
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── ADMIN ────────────────────────────────────────────────────────────
ADMIN_MENU_KEYBOARD = [
    [InlineKeyboardButton("🔨 Ban User", callback_data="admin_ban")],
    [InlineKeyboardButton("🔓 Unban User", callback_data="admin_unban")],
    [InlineKeyboardButton("🔑 Generate Key", callback_data="admin_genkey")],
    [InlineKeyboardButton("👥 View Users", callback_data="admin_viewusers")],
    [InlineKeyboardButton("📊 Rankings", callback_data="admin_rankings")],
    [InlineKeyboardButton("📢 Broadcast", callback_data="admin_sendmsg")],
    [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
]
ADMIN_MENU = InlineKeyboardMarkup(ADMIN_MENU_KEYBOARD)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You are not an admin.")
        return
    await update.message.reply_text("🔧 Admin Panel", reply_markup=ADMIN_MENU)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.edit_message_text("⛔ Not admin.")
        return
    data = query.data

    if data == "admin_ban":
        await query.edit_message_text("Send the user ID or username to ban.\n/cancel to abort.")
        context.user_data["admin_action"] = "ban"
        return
    if data == "admin_unban":
        await query.edit_message_text("Send the user ID or username to unban.\n/cancel to abort.")
        context.user_data["admin_action"] = "unban"
        return
    if data == "admin_genkey":
        keyboard = [
            [InlineKeyboardButton("30 seconds", callback_data="key_dur_30")],
            [InlineKeyboardButton("5 minutes", callback_data="key_dur_300")],
            [InlineKeyboardButton("1 hour", callback_data="key_dur_3600")],
            [InlineKeyboardButton("1 day", callback_data="key_dur_86400")],
            [InlineKeyboardButton("1 month", callback_data="key_dur_2592000")],
            [InlineKeyboardButton("1 year", callback_data="key_dur_31536000")],
            [InlineKeyboardButton("Lifetime", callback_data="key_dur_0")],
            [InlineKeyboardButton("Cancel", callback_data="admin_close")],
        ]
        await query.edit_message_text("Choose duration for the key:",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if data.startswith("key_dur_"):
        dur = int(data.split("_")[2])
        context.user_data["genkey_duration"] = dur
        await query.edit_message_text(
            "Send the number of keys to generate (1-100).\n/cancel to abort."
        )
        context.user_data["admin_action"] = "genkey_quantity"
        return
    if data == "admin_viewusers":
        users = get_all_users()
        if not users:
            await query.edit_message_text("No users registered.")
            return
        lines = []
        for uid, uname, admin_flag, is_prem, banned, count in users[:20]:
            uname = uname or f"User {uid}"
            admin_tag = "👑" if admin_flag else ""
            prem_tag  = "⭐" if is_prem else ""
            ban_tag   = "🚫" if banned else ""
            today     = get_daily_count(uid)
            lines.append(
                f"{admin_tag}{prem_tag}{ban_tag} {uname} (ID:{uid}) – "
                f"{count} total | {today}/{DAILY_FREE_LIMIT} today"
            )
        await query.edit_message_text("👥 Users (first 20):\n" + "\n".join(lines))
        await query.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)
        return
    if data == "admin_rankings":
        users = get_top_users(10)
        if not users:
            await query.edit_message_text("No users.")
            return
        lines = ["🏆 Top Lookup Users"]
        for idx, (uid, uname, count) in enumerate(users, 1):
            uname = uname or f"User {uid}"
            if uid in ADMIN_IDS:
                uname = f"👑 {uname}"
            lines.append(f"{idx}. {uname} – {count}")
        await query.edit_message_text("\n".join(lines))
        await query.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)
        return
    if data == "admin_sendmsg":
        await query.edit_message_text("Send the message to broadcast to all users.\n/cancel to abort.")
        context.user_data["admin_action"] = "sendmsg"
        return
    if data == "admin_close":
        await query.edit_message_text("Closed.")
        await query.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)
        return

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_chat(update.effective_chat):
        return
    if not is_admin(update.effective_user.id):
        return
    action = context.user_data.get("admin_action")
    if not action:
        return
    text = update.message.text
    if text.lower() == "/cancel":
        context.user_data.pop("admin_action", None)
        context.user_data.pop("genkey_duration", None)
        await update.message.reply_text("Cancelled.", reply_markup=ADMIN_MENU)
        return

    if action in ("ban", "unban"):
        target = None
        if text.isdigit():
            target = get_user(int(text))
        else:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username LIKE ?", (text,))
            row = c.fetchone()
            conn.close()
            if row:
                target = {"user_id": row[0]}
        if target:
            if action == "ban":
                ban_user(target["user_id"])
                await update.message.reply_text(f"{E_CHECK} Banned user {target['user_id']}.",
                                                parse_mode="HTML")
            else:
                unban_user(target["user_id"])
                await update.message.reply_text(f"{E_CHECK} Unbanned user {target['user_id']}.",
                                                parse_mode="HTML")
        else:
            await update.message.reply_text("User not found.")
        context.user_data.pop("admin_action", None)
        await update.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)

    elif action == "genkey_quantity":
        try:
            quantity = int(text.strip())
            if not 1 <= quantity <= 100:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Please enter a valid number between 1 and 100.")
            return
        dur = context.user_data.get("genkey_duration", 0)
        keys = [generate_key(dur) for _ in range(quantity)]
        if dur == 0:
            dur_str = "Lifetime"
        elif dur < 60:
            dur_str = f"{dur} seconds"
        elif dur < 3600:
            dur_str = f"{dur//60} minutes"
        elif dur < 86400:
            dur_str = f"{dur//3600} hours"
        elif dur < 2592000:
            dur_str = f"{dur//86400} days"
        elif dur < 31536000:
            dur_str = f"{dur//2592000} months"
        else:
            dur_str = f"{dur//31536000} years"
        key_list = "\n".join(f"<code>{k}</code>" for k in keys)
        await update.message.reply_text(
            f"{E_CHECK} Generated <b>{quantity}</b> key(s)\n"
            f"{E_KEY} Duration: {dur_str}\n\n{key_list}\n\n"
            f"{E_CROWN} https://t.me/zyrondevshop/47",
            parse_mode="HTML",
        )
        context.user_data.pop("admin_action", None)
        context.user_data.pop("genkey_duration", None)
        await update.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)

    elif action == "sendmsg":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        rows = c.fetchall()
        conn.close()
        sent = 0
        for (uid,) in rows:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error("broadcast fail %s: %s", uid, e)
        await update.message.reply_text(
            f"{E_ANNOUNCE} Broadcast sent to <b>{sent}</b> users.", parse_mode="HTML"
        )
        context.user_data.pop("admin_action", None)
        await update.message.reply_text("Admin Panel", reply_markup=ADMIN_MENU)

# ── BOOTSTRAP ────────────────────────────────────────────────────────
async def post_init(application: Application):
    global _LOOKUP_EXECUTOR
    from concurrent.futures import ThreadPoolExecutor
    _LOOKUP_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ml_lookup")
    application.create_task(queue_worker())
    logger.info("Bot ready. Executor pool started. Daily free limit: %s "
                "Lookup retries per request: %s",
                DAILY_FREE_LIMIT, MAX_LOOKUP_RETRIES)

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lookup", lookup_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("usage", usage_command))
    app.add_handler(CommandHandler("rankings", rankings_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^key_dur_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))

    print(f"Bot started. Free daily limit: {DAILY_FREE_LIMIT}. "
          f"Lookup retries: {MAX_LOOKUP_RETRIES}. Ctrl+C to stop.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
