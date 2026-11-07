import requests
import uuid
import time
import hashlib
import urllib3
import zlib
import zstandard as zstd
import socket
import logging
import datetime
import random
import struct
import threading
import sys
import os
import json
from colorama import init, Fore, Style
from enum import Enum
from typing import Any, Tuple
from Crypto.Cipher import AES
from curl_cffi import requests as curl_requests

init()

# ── GLOBAL MODE FLAGS ────────────────────────────────────────────────
DEBUG_MODE   = False
VERBOSE_MODE = False

# ── DEBUG HELPERS ────────────────────────────────────────────────────
def dbg(label, data=None, color=Fore.MAGENTA):
    """Print a debug message only when DEBUG_MODE is on."""
    if not DEBUG_MODE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if data is None:
        print(f"{color}[DBG {ts}] {label}{Style.RESET_ALL}")
    else:
        print(f"{color}[DBG {ts}] {label}{Style.RESET_ALL}")
        if isinstance(data, (bytes, bytearray)):
            hex_str = data.hex()
            for i in range(0, len(hex_str), 64):
                print(f"  {Fore.CYAN}{hex_str[i:i+64]}{Style.RESET_ALL}")
        elif isinstance(data, dict):
            for k, v in data.items():
                print(f"  {Fore.CYAN}[{k}] => {repr(v)[:120]}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.CYAN}{repr(data)[:200]}{Style.RESET_ALL}")


HERO_ID_MAP = {
    1: "Miya", 2: "Balmond", 3: "Saber", 4: "Alice", 5: "Nana", 6: "Tigreal", 7: "Alucard", 8: "Karina", 9: "Akai",
    10: "Franco", 11: "Bane", 12: "Bruno", 13: "Clint", 14: "Rafaela", 15: "Eudora", 16: "Zilong", 17: "Fanny",
    18: "Layla", 19: "Minotaur", 20: "Lolita", 21: "Hayabusa", 22: "Freya", 23: "Gord", 24: "Natalia", 25: "Kagura",
    26: "Chou", 27: "Sun", 28: "Alpha", 29: "Ruby", 30: "Yi Sun-shin", 31: "Moskov", 32: "Johnson", 33: "Cyclops",
    34: "Estes", 35: "Hilda", 36: "Aurora", 37: "Lapu-Lapu", 38: "Vexana", 39: "Roger", 40: "Karrie", 41: "Gatotkaca",
    42: "Harley", 43: "Irithel", 44: "Grock", 45: "Argus", 46: "Odette", 47: "Lancelot", 48: "Diggie", 49: "Hylos",
    50: "Zhask", 51: "Helcurt", 52: "Pharsa", 53: "Lesley", 54: "Jawhead", 55: "Angela", 56: "Gusion", 57: "Valir",
    58: "Martis", 59: "Uranus", 60: "Hanabi", 61: "Chang'e", 62: "Kaja", 63: "Selena", 64: "Aldous", 65: "Claude",
    66: "Vale", 67: "Leomord", 68: "Lunox", 69: "Hanzo", 70: "Belerick", 71: "Kimmy", 72: "Thamuz", 73: "Harith",
    74: "Minsitthar", 75: "Kadita", 76: "Faramis", 77: "Badang", 78: "Khufra", 79: "Granger", 80: "Guinevere",
    81: "Esmeralda", 82: "Terizla", 83: "X.Borg", 84: "Ling", 85: "Dyrroth", 86: "Lylia", 87: "Baxia", 88: "Masha",
    89: "Wanwan", 90: "Silvanna", 91: "Cecilion", 92: "Carmilla", 93: "Atlas", 94: "Popol and Kupa", 95: "Yu Zhong",
    96: "Luo Yi", 97: "Benedetta", 98: "Khaleed", 99: "Barats", 100: "Brody", 101: "Yve", 102: "Mathilda",
    103: "Paquito", 104: "Gloo", 105: "Beatrix", 106: "Phoveus", 107: "Natan", 108: "Aulus", 109: "Aamon",
    110: "Valentina", 111: "Edith", 112: "Floryn", 113: "Yin", 114: "Melissa", 115: "Xavier", 116: "Julian",
    117: "Fredrinn", 118: "Joy", 119: "Novaria", 120: "Arlott", 121: "Ixia", 122: "Nolan", 123: "Cici",
    124: "Chip", 125: "Zhuxin", 126: "Suyou", 127: "Lukas", 128: "Kalea", 129: "Zetian", 130: "Obsidia"
}

# ── SKIN DATABASE ────────────────────────────────────────────────────
import json as _json
_SKIN_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skin_db.json')
try:
    with open(_SKIN_DB_PATH, 'r', encoding='utf-8') as _f:
        _raw = _f.read().strip()
        if not _raw.startswith('{'):
            _raw = '{' + _raw
        SKIN_DB = _json.loads(_raw)
except Exception:
    SKIN_DB = {}

SKIN_TIER_LABELS = {
    'common':      'Common', 'exceptional': 'Exceptional', 'deluxe':      'Deluxe',
    'exquisite':   'Exquisite', 'grand':       'Grand', 'supreme':     'Supreme',
    'unknown':     'Unknown',
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
        (160000, 280000, "Mega Collector"), (280000, float('inf'), "World Collector"),
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
        {"min": 10,  "max": 14,  "rank": "Warrior I"}, {"min": 15,  "max": 19,  "rank": "Elite IV"},
        {"min": 20,  "max": 24,  "rank": "Elite III"}, {"min": 25,  "max": 29,  "rank": "Elite II"},
        {"min": 30,  "max": 34,  "rank": "Elite I"}, {"min": 35,  "max": 39,  "rank": "Master IV"},
        {"min": 40,  "max": 44,  "rank": "Master III"}, {"min": 45,  "max": 49,  "rank": "Master II"},
        {"min": 50,  "max": 54,  "rank": "Master I"}, {"min": 55,  "max": 59,  "rank": "Grandmaster IV"},
        {"min": 60,  "max": 64,  "rank": "Grandmaster III"}, {"min": 65,  "max": 69,  "rank": "Grandmaster II"},
        {"min": 70,  "max": 74,  "rank": "Grandmaster I"}, {"min": 75,  "max": 81,  "rank": "Epic IV"},
        {"min": 82,  "max": 88,  "rank": "Epic III"}, {"min": 89,  "max": 95,  "rank": "Epic II"},
        {"min": 96,  "max": 107, "rank": "Epic I"}, {"min": 108, "max": 114, "rank": "Legend IV"},
        {"min": 115, "max": 121, "rank": "Legend III"}, {"min": 122, "max": 128, "rank": "Legend II"},
        {"min": 129, "max": 135, "rank": "Legend I"},
        {"min": 136, "max": 160, "rank": lambda p: f"Mythic {p - 135}"},
        {"min": 161, "max": 195, "rank": lambda p: f"Mythical Honor {p - 135}"},
        {"min": 196, "max": 235, "rank": lambda p: f"Mythical Glory {p - 157}"},
        {"min": 236, "max": 999, "rank": lambda p: f"Mythical Immortal {p - 157}"},
    ]
    for entry in RANK_DEFINITIONS:
        if entry["min"] <= p <= entry["max"]:
            rank = entry["rank"]
            return rank(p) if callable(rank) else rank
    return "Unknown"


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ── BAN DETECTION (aligned with banv22.py, but stub-safe) ───────────
BAN_REASONS = {
    '1':  'Verbal Abuse / Inappropriate Avatar or Name',
    '2':  'Toxic Behavior / In-Game Chat Violation',
    '3':  'Intentional Feeding / AFK / Griefing',
    '7':  'Illegal Diamond Top-up / Refund Fraud',
    '21': 'Using Plug-in Apps to Compromise Competitive Fairness',
    '22': 'Account Security Risk / Fraudulent Activity',
    '23': 'Unauthorized Account Access',
    '24': 'Cheating in Ranked Match',
    '25': 'Payment Fraud / Chargeback',
    '26': 'Account Trading / Sale',
    '88': 'Device Hardware Ban (HWID)',
    '99': 'Permanent System Security Violation',
}


def _walk_ban(obj, out, depth=0):
    """Recursively scan a parsed SDP dict for ban-related tags.

    Only meaningful values are recorded:
      • endtime_day > 0   → stored
      • endtime_day > 1e9 → stored (epoch)
      • endtime_day == 0  → stored as a placeholder; final decision is
                            made by inspect_ban using sub-day fields
      • endtime_hour/min/sec only stored when truthy
      • ban_reason stored as ban_code WITHOUT auto-marking banned
      • ban_status_raw only stored when scalar and truthy
      • other ban_* keys only when truthy and scalar
    """
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()

            if k == 'ban_reason':
                code = str(v)
                if code and code not in ('0', '', 'None'):
                    out.setdefault('ban_code', code)
                    out.setdefault(
                        'reason_name',
                        BAN_REASONS.get(
                            code,
                            'Using Plug-in Apps to Compromise Competitive Fairness'))
            elif k == 'endtime_day':
                if v is None:
                    continue
                try:
                    iv = int(v)
                except (TypeError, ValueError):
                    iv = None
                if iv is None:
                    out['endtime_day'] = v
                elif iv > 0:
                    out['endtime_day'] = iv
                else:
                    # 0 → record but inspect_ban decides based on sub-day
                    out.setdefault('endtime_day', 0)
            elif k == 'endtime_hour':
                if v not in (None, 0, '0', ''):
                    out['endtime_hour'] = v
            elif k == 'endtime_min':
                if v not in (None, 0, '0', ''):
                    out['endtime_min'] = v
            elif k == 'endtime_sec':
                if v not in (None, 0, '0', ''):
                    out['endtime_sec'] = v
            elif k == 'ban_status' or 'ban_status' in k_lower:
                # ignore nested structs, only scalars
                if isinstance(v, (dict, list)):
                    pass
                elif v not in (None, 0, False, '0', ''):
                    out['ban_status_raw'] = v
            elif k_lower.startswith('ban_') and k not in ('ban_reason', 'ban_status'):
                if isinstance(v, (dict, list)):
                    pass
                elif v not in (None, 0, False, '0', ''):
                    out.setdefault(str(k), v)

            if isinstance(v, (dict, list)):
                _walk_ban(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_ban(item, out, depth + 1)


def _looks_like_player(sdp):
    """True when the SDP payload carries real player identity fields.

    A stub payload (empty account, 'not found' reply) has no nickname,
    level, country or location — but frequently carries placeholder
    endtime_* fields which would trigger a false ban.
    """
    if not sdp:
        return False
    try:
        nick = sdp.get(2)
        lvl  = sdp.get(3)
        cc   = sdp.get(97)
        loc  = sdp.get(71)
        # nickname string
        if isinstance(nick, str) and len(nick.strip()) > 0:
            return True
        # level > 0
        if isinstance(lvl, int) and lvl > 0:
            return True
        # country code present
        if isinstance(cc, str) and len(cc.strip()) > 0:
            return True
        # location list
        if isinstance(loc, list) and len(loc) >= 2:
            return True
    except Exception:
        return False
    return False


def inspect_ban(sdp):
    """Decide whether an SDP payload represents a ban.

    Rules (matching real MLBB wire behaviour, stub-safe):

      • Non-player payload → CLEAN unless ban_status_raw is 1/true/yes.
      • endtime_day > 1_000_000_000             → BANNED (epoch expiry)
      • endtime_day > 0                          → BANNED (N-day ban)
      • endtime_day == 0 AND 0<total≤24h AND h≤23 → BANNED (sub-day ban)
      • endtime_day == 0 with no valid sub-day   → CLEAN
      • endtime_day absent                       → CLEAN
        (unless ban_status_raw is 1/true/yes)
      • ban_reason alone                         → CLEAN
    """
    info = {}
    if sdp:
        try:
            _walk_ban(dict(sdp), info)
        except Exception:
            pass

    # ── stub gate ──────────────────────────────────────────────────
    if not _looks_like_player(sdp):
        raw = info.get('ban_status_raw')
        if raw is not None and str(raw).strip().lower() in ('1', 'true', 'yes', 'banned', 'ban'):
            info.setdefault('ban_code', '21')
            info.setdefault('reason_name', BAN_REASONS['21'])
            return True, info
        return False, {}

    banned = False
    day = info.get('endtime_day')
    has_hms = any(
        info.get(f'endtime_{u}') not in (None, 0, '0', '')
        for u in ('hour', 'min', 'sec')
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
                h = int(info.get('endtime_hour', 0) or 0)
                m = int(info.get('endtime_min', 0) or 0)
                s = int(info.get('endtime_sec', 0) or 0)
                total = h * 3600 + m * 60 + s
                if 0 < total <= 24 * 3600 and h <= 23:
                    banned = True
                # else: placeholder → CLEAN
        else:
            # non-numeric day value → only trust if sub-day present
            if has_hms:
                banned = True

    if not banned:
        raw = info.get('ban_status_raw')
        if raw is not None and str(raw).strip().lower() in ('1', 'true', 'yes', 'banned', 'ban'):
            banned = True
            info.setdefault('ban_code', '21')
            info.setdefault('reason_name', BAN_REASONS['21'])

    if banned:
        if not info.get('reason_name'):
            code = info.get('ban_code') or '21'
            info['ban_code'] = code
            info['reason_name'] = BAN_REASONS.get(
                code, 'Using Plug-in Apps to Compromise Competitive Fairness')
        return True, info

    return False, {}


def format_ban_duration(info):
    """Human ban duration. Returns None when there is no real ban."""
    day = info.get('endtime_day')
    if day is None:
        return None

    h = int(info.get('endtime_hour', 0) or 0)
    m = int(info.get('endtime_min', 0) or 0)
    s = int(info.get('endtime_sec', 0) or 0)

    try:
        d = int(day)
    except (TypeError, ValueError):
        return None

    if d > 1_000_000_000:
        return f"until {format_timestamp_full(d)}"

    if d > 0:
        return f"{d}d {h:02d}h {m:02d}m"

    # d == 0
    total = h * 3600 + m * 60 + s
    if 0 < total <= 24 * 3600 and h <= 23:
        return f"{h:02d}h {m:02d}m {s:02d}s"

    return None


def extract_bindings(player_data):
    """Infer linked accounts from player dict (mirrors ZY_DEVID1.py)."""
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
        if "google"   in low and "Google"   not in binds: binds.append("Google")
        if "tiktok"   in low and "TikTok"   not in binds: binds.append("TikTok")
        if "apple"    in low and "Apple"    not in binds: binds.append("Apple")
    return ", ".join(dict.fromkeys(binds)) if binds else "Device Only"
# ── end ban/bindings block ───────────────────────────────────────────


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
        self.data = b''
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
            encoded = value.encode('utf-8') if isinstance(value, str) else value
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
                value = self._read_number().to_bytes(4, 'little')
                return tag, struct.unpack("<f", value)[0]
            elif data_type == SdpDataType.DOUBLE:
                value = self._read_number().to_bytes(8, 'little')
                return tag, struct.unpack("<d", value)[0]
            elif data_type == SdpDataType.STRING:
                length = self._read_number()
                try:
                    value = self.data[self.offset:self.offset+length].decode('utf-8')
                except UnicodeDecodeError:
                    value = self.data[self.offset:self.offset+length]
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
        if isinstance(other, SdpStruct):
            super().update(other)
        else:
            super().update(other)
        self._pack_to_binary()


VERBOSE_MODE = False

DEVICE_IDS = [
    'and_a01476090ccb450e255426d014802b93xx7dl43sippc1q4od5a87c27-7f12-4204-8d0e-6ed5648457e9',
    'and_c92437c75572f50783dae442d90bf15aj1vxxcqw23v0r8hx5fc92e18-6530-4522-88fc-2976ada3f320',
    'and_ed0a324c6c32f4c8bc7dbf4b97545c86i9l6e7iopkmo07v8ed279800-babb-42d9-9999-bf5277f227f2',
    'and_abcc47f66ca0cdbccfe14af6e816666d3bgcemt0qqk72erz40fab465-1a30-4869-b5bd-dfa92a77fa0b',
    'and_4d94689a69eb344c8f62645755b88b49zdd0klzxqd4otbc2b00fefa0-d281-43d1-9d40-dd210e8fd8c0',
    'and_f07a0aa6a164713de2542bb189f9304ecs32ng1sm1tt93db635d3586-d372-4c74-914a-deb2ba942d97',
    'and_900b1685b4b25f9bc8ca8062edd8fd9a9l7cchqh1r1waxms82c1ac2b-cc56-41b7-a836-0c1a29751d08',
    'and_489288d82f7845d8407af3209e92c330z49v5njqoeq2ldidcd17b973-7dbd-4f65-a327-594924b4b3f4',
    'and_0ebed1b98462c68145949ff305bb8ecf99bc223ebc129fe34b254b0d-371b-4e7b-b29f-e073a247d1df',
    'and_0b27aaac5d853494f85b865c76f5759epaatmwmuf17crp6f5950d832-fc7b-4505-8fb8-ad0905fab000',
    'and_8e5cbda12ba78e2a546f0577bc46eb328ce0d9836d4ea93d0e9476aa-98e9-4541-bc47-cab4ddd622ad',
    'and_16e209601e6df7b08689b74952dc672deece8bc20b9d400264e85256-515f-44a3-837f-5c6932aeacc8',
    'and_bbe8decb4e28afb044b5db6fa13ea2d4husuzy9byf6culhl76a4b1da-dc50-479e-aae9-c31d1e2af5c4',
    'and_7ad099ceb6afd7319d0b51dce9e47e5384eb1c733194c396023c3b15-241c-4b6c-b490-9c20d66965be',
    'and_d435476f2ff8e6804125d391c9842b5f9f00662ea01e259fb830be2d-ef95-4adf-8557-a138dd21a1eb',
    'and_581e59aba5aeb8cd65405e80b6571c45d4b000fe764d3d5a7142b20b-0cf9-4aca-83ff-9d163d1658f7',
    'and_58a3d616961d541f20084f0a57fe6f0210jz2w8o8b1vvh5sa8d31ae8-8a0c-4b40-9b8d-a88b10d82255',
    'and_127fd2d8e4aed4b9f1954f6bc6163a6eo2wjky6ri2wwwck32a20290a-2d69-4c23-bf77-fd2da18c9b62',
    'and_58b8aed761014908dced84c3ce20ac0bb23429ef9b0021deb96a337e-25b8-47ab-9c14-eeab893e4e9a',
    'and_1245820c8ce08f31305e9bd43feebf3cbwybmilnk3jbgud60fc14016-073e-497c-8a7f-49dd1a3f0d8a',
    'and_66f0b67c138eb0ceffc6ec96d8cfe6b1dbb468c8fa85a98f85a6cf77-e7bf-4180-9736-3b26654c9a54',
    'and_22be2508db86d24867f43cd60f88cd88z7r3zieu70cmqbb3d523a958-09e7-46f3-aeb9-f1be999eb240',
    'and_716d8fc7832a3a00501ba7bcb204edd7ps497uplrez70zibb347e993-1da0-4ff6-8483-5cb9cf4a9a08',
    'and_4705d9f347f8c64e9d9cd37b7c8786bd876343szyoayln80bf861184-e7b4-47d7-b39f-dc3c1b636307',
    'and_99f38aa622b4f83fda2364f5fa9b9fe65qvvdz6fkp4n42suef194054-ccfa-4eb7-b128-cfaa7b707a3a',
    'and_75f7da529422b1bee64d141164041b61utgkscjz1521cltte73f2a28-8fe7-46f5-9573-96ee2dd1425b',
    'and_b1f8763d93e924fb94c528326440b4cem5s8u7j24021w9ja26c15f55-c179-4441-a74a-2f60f365fb4a',
    'and_fb38f51a1f7fba974f24ec8eb6f5943am4o08v8zufgtne4abb6d9811-62c0-4fe7-b6e6-42269288db23',
    'and_0c4212a22179a9519041e7440d3bcdaclziueb9ta3k335lv1d8b8188-aa07-41ff-9d8a-8870d0a45681',
    'and_1470cdcf04f5eacf09be4e0b2a98409c1t21a0rwuvdhlnqe62d4a95e-9f17-45c0-afc6-fec98c59812e',
    'and_4f76cc5d17036a73e6eec3e66069da37qbsfv7zbcby4tcf592df806a-5f7d-4bae-9121-c2ccdbe1b01d',
    'and_8da7053c915d0c128f33df6c9101890dd190zkcpir1m6wq9f574f14e-a90d-4b5f-97c0-022f69b36bc0',
    'and_c84990cc8a9e554db2f55c2713191ed1oo8mbdu07aqedyd8d0a19e71-071d-4394-9df6-a7864a1fa6ed',
    'and_5241f3f9e0cd910e46cfb8dc353919dd3s6ec3aoms6qumb24ca239c5-d0f3-40ea-8b3d-bacb2d1b801c',
    'and_d8c8e737ddb30a162f6e342ca05cf639woiws74ik3zlsexpc2729ace-5321-4a7c-beaf-fc159efff82f',
    'and_12dcac88ad1f35aa11c02e3a20c556b5tvd1aj1bystf4xnfd031ad5e-e69e-4992-b3bb-4b6314c69dd2',
    'and_411241876a851201fb0b0c332847733et5ij1t22oncvxzp5a0ae7dfe-c29c-4f43-a43f-071f70f99268',
    'and_e2cc6d33b3947eb67e6074d2649579d835pjb39i06k8xqumfc8364fb-8f59-481e-bb73-9bfda37cf546',
    'and_6215cb3b5f5f4e1fda73006cde2e213axelyfnggasy9u9wq425141ef-1501-4f27-a8de-a8b84356efb2',
    'and_905da56875df6bc765059beee38ec0fah08dpcpavnsk1veo05dbbc86-16e8-43e0-a578-23d313d07d27',
    'and_d49997cb3a21d40d5081e0524a269690rkwz19ovoyytzwxr09b2f263-93d7-4c6f-9e20-751dd72fbbfa',
    'and_232cdb5fc156e1ee212a8149ef27554arwj1xhorq3bt4g7m5dc996c8-cb4e-40ab-b0f1-70df82a44086',
    'and_f339f637c98a3fde81a27e5cd879316fy04dfwcffx89827a14bdbb55-0301-451d-9b20-73724acef5bc',
    'and_50d7043eea98f5173eb85e231dfd7baadjvdsv775y0z5qyw9b5a6370-ee6d-4141-8a25-d579381c41f2',
    'and_81085cd3d233f13750864bef9a9a77bc18f0jlma6nrfyb7id132f7f3-7d34-4fc1-b5f0-fab473300bc1',
    'and_56e4e219c5f621eb72e50ce3dcba8bbebrz4i4gkltkm2ty5baf56e92-e306-491a-a056-3ba4d58104c0',
    'and_5e97d0b255efd2bc509db64808f07c3dbi4e1w03ft6t2o64c427aa78-ecbd-45dc-9533-ff9f3670a05b',
    'and_f75afe9185a911eb3bcc6c57041ea70ca5i702tw18brgeh2ec8b9712-5eb5-4c35-accc-63dfe5ecac94',
    'and_65a55d4a1bcc92e35518d8a46c5e8cfash3ulwy4sqphrhwp0739d122-44b9-47c5-8ed3-574954ab6c4b',
    'and_bbd0399f99b32290a47e9f07fe3fe490aqwjwcpjtvhtt5uk97b5ed12-f63e-42f6-a1d8-644d7a35d0d7',
    'and_521117b00b848d4d4aff3c730e6bf0480xhc2cpz2niq05rj340b2773-f1fb-42a8-95ca-e1f1cc207034',
    'and_547cd1265b36979504f6f1ac5b3d383ew4kj771xxxxl4cjheef13fad-14e0-4a7e-8feb-0cc2ce52d667',
    'and_c816adde3388595a91f5355b24c12d28tznr0xxnw28228rt33d0533b-c7a0-49a7-b16c-a55b6c8f9d40',
    'and_c42477c542fc007b8f911f00ad9b520er5ffzmn7mpmh6upz3839bc14-2257-4c63-83de-1a87f396d153',
    'and_d07ccc3d1136f17b4c67687fff9d1446awziy9n4zvyqmc8t0bd0bf3a-fda3-4fbf-bc6d-32aa685097c5',
    'and_25c3c18dcc84ce711e2474eeeee6b4aa03kn2be5nr52jnn3b52eb32d-e00b-4b1c-8b00-3c655ffa32cd',
    'and_ac61c7410f97b429d51e648a3fdd251bktltjp4sc2o6ywr8f43a1185-bced-4a00-80e1-300ed76ec257',
    'and_6e95cf1b4c8b5c025f41a54507eb8592u8fyskydd54o7hov43efc643-11a4-4606-8197-6eac0f48c2f9',
    'and_147d4c145b2a4e23bc05f48e1f578eb60vccfeesw7usyu522f6e950c-38f9-47b9-9d4d-a3729950fe8f',
    'and_517e4f4d86c8574debf579d04275dab3c7409252sspczzmf28cedbf3-2567-47fb-b73b-8ac434154d45',
    'and_06ec1b4f81235b1d82b99543bc64be0089x6rn3kt6epmvbt572a97af-c7cb-4094-b44e-26a21ccab826',
    'and_96a2459e378e8670c33321f36d7be1ebs7eu4eirqkmb7rzg3bfdd0fa-f9e9-4e28-a6ee-6601b3a861f0',
    'and_89cc0e51e93f34339457e5779d8279b0ge1ufffhpjq6qeske050eaa4-0a52-4fc3-a5cb-b44228cb39f0',
    'and_ee9b48cc6590bd96f98aa8a03961000d038rnbykefuaqh6f96539978-c494-40a5-91c9-f34a399156f8',
    'and_5b6ff11598f4ff2e5d58b4be6055c052buxe951m7f7vm36o73b22ada-facc-43ad-9041-cec87ccb92de',
    'and_bf7b1456e7519a62eb1d60893892b2b4i556axvn2v8nge7oddce0f67-64a7-40e9-a998-e1819e734f1e',
    'and_9764f681acfa7f0cec7265e7e480b7886vwo3y3a8qa9ylaw358f01d8-175b-4d64-9b45-23d628ea54c1',
    'and_41fbafb87a454559e1ca3034ad233958ygy01i26a9bfbdzxab654adb-0e94-4fee-b43c-34ac7622fecc',
    'and_667d11eb9e393d350de3c9534bb8a243irs6cdkna9u7zfq022df64cb-f452-4cee-90cf-3eb878d76bb5',
    'and_21ad4da6fc441ed5e60a24f32557577aiy9t667lph814a7sd41faff9-e73c-4141-a595-1ee649b5698b',
    'and_709853ff7913b87879b79eb7822ac6a0ess6rbt4ofj0bdm6b84ffc9e-0e90-4abd-8a71-bb399b5edc3c',
    'and_a954cc0157e06d2624e1fd1de8ff97bbmvzu25r3s6d0ubhg216e6b3d-6cbd-40fa-a328-ba14ac704b95',
    'and_693898ee43b96998693bb7bc1ec7a419nxfy3ksycogxfcw2088b0a3a-ff1a-486d-ad79-65e0e52d7c0e',
    'and_e62bda47e47520ce06df58f9d1246c59qnjgmct1okp4znvd0ec7974a-d7d2-4b9b-a25f-26713a9fc553',
    'and_2514e2d1e2defd58bedc3bbec65b6da8dcykl95egsm64ppfb838161f-eae7-4ad0-9962-b131e5254aa4',
    'and_c0be2cdc0884e69fb71ba5d46f5462a024gbf5wcynh23ega6fab7626-4178-4a7e-ac51-90c205087990',
    'and_6418cd63223a6b9d61b4e9a935fa3610btmfjcsxeowd7z5ha1bebbe2-ab15-4a90-af70-468380500756',
    'and_1390ad6313632bccfaa072fd7e5d8ee0iv7xtpw0rs312xiree48d6b6-09c4-4f1e-9c6f-b3ca09b0a171',
    'and_c801d0c813da16884a775b9076e2344eo7o3hkbgzxksx0x04ae27a72-46c4-4f3e-9505-a39a2c315241',
    'and_4a901a54e2b28e04de6a10c10b6ec2bc7jfz9zfq9aqrtvyw5e2f215e-ef69-406d-993d-80b51aa77fd9',
    'and_58d0ad8fd48774d19a0684af35dc68d53i576geeydtcqo0p33f2770b-de14-4216-9e37-9a3f3b0351aa',
    'and_ddae47d750de4bdf8df89403c815ebcb7m4w8ypu8e8i0i4g4d939ef2-f414-46e6-8149-017025d8dcee',
    'and_8ec3c468596a5f362479b229885be6a88vz2fky9g51hwsle38f1a61a-1f59-4255-b3d6-bb9593811248',
    'and_dfe929119f64109a3464b9d77baaea930fe5kzgw09a7u7jq88edef65-f5ce-4450-b38a-ed5f4e73610a',
    'and_3f598ff8c9a2ead1bbe99e0391c43c86mkfrqi0rk2rsxee4c8fd2fa9-f953-4fb9-ab60-a1f7a2c3d7e4',
    'and_bb7ac04218d45209cffdc8be5807f32010jii7yxzf4eh3in6e53081b-e229-4ccf-ae6c-59239adf4c07',
    'and_7fae5daa7fd1a37a442feaa5d4ea994299c5jlb6wsy937mja6891af6-d48b-43e5-ab2d-e5ecd0a9b60b',
    'and_b5cdeea84d8da1efe5c18838fd590e3avoph2k5m0pswhfrpd5efc3de-3129-4530-bac9-6b3aef02dfd1',
    'and_7f56fe5c1da8a2289287c0cac137f0c631ddy92sxislns62fc5f9ba7-b7f7-4763-9041-f876434f49f0',
    'and_cf5a0ece3114b57f53b0a38596cb2350frufmxmmsn1lnncrf6478972-ead5-444e-86c4-48d3beb11a6a',
    'and_dc07d08ba6f49668f14e32676fedbde0jen1qdvd25j9dg8x7ef2e9b3-0ed9-4c87-9387-96a7a80d1381',
    'and_42d8a97b5d17142253d2402dd8231bdb7b1jdtb10uxtiktf4b927b32-aac4-47d4-a264-ba8f79839a61',
    'and_1d35338182f2d501d9de25fea22a5535ythpquc8ovwdt4wcba654ed5-55a5-4141-bb00-e919dc165d47',
    'and_f356706462969d84518e5b7386beba47c45euzuliu5e5nrjc05aa2d0-a059-49c4-bd1d-64c3e1856349',
    'and_172eb1f2987fa714a2ac187bf2846fb5bismn30naly1cox02cb5203e-dd0a-4326-9c2c-9191a196fc05',
    'and_04edba1213cede597df3ec7569b2c310p04jtudm4r2dpzm4c3ad0c1e-abf6-4fa2-84f6-16ab572b2d88',
    'and_7c214944f020ad3cef133b498d479881ar4aqk0902yt5u4o1668a98b-aef7-491b-a2a4-e0a6ee4dee4d',
    'and_f5a096cb145e460413bdce0485b3a3579nmsixq0r5ehs08p026dae76-5221-4133-a88b-6df110d292ae',
    'and_2726042a8195347111fef0cc4eaf8264348oavl892yx9qsb4f52079e-56c8-42a5-95ae-dec4e3d7288e',
    'and_1140cceb03797c942933219a4144582bcmkc6nrnl087zm2aa640489a-adad-4747-8d38-3092534d9593',
    'and_030286153ce8e3434572b396d9d1b95d2g1coz8wlwns08flc50dd9fd-1a96-4f41-8175-bf7a77cb8ced',
    'and_cbb28804f125adbcf8da5e04ddc90d69l2ntz7mdipo75jizb00d9e7c-f873-49d7-bb19-979f952fa3d0',
    'and_e0582edcaab275c0b11099b357d29321qaoxuwbhhg4zzq2o12fbace7-ce36-40cc-953a-5b9ae555ae16',
    'and_46d80aa58176a2979327f0aac2dc73b0fb9ri8bool6naxnr0fa568c2-874b-4e64-a01f-649c93a2a00f',
    'and_b8f8b841cf55db52459b7729d585c91c4ota7xskh51dmsbydd0a7132-7fee-4525-80c6-3c561915325f',
    'and_105af9c27ea8d281d0b4b3b38b2bbd90pc44sthk3ajactm360a5650d-155f-4721-a459-e5d48dbfaf76',
    'and_3e18214af53cd3b06642151a81750cecs89nsfyqyl8mutai1a190d7c-3fa5-4603-a33b-a7b4c96f28ed',
    'and_979ba5bb4923fd673959e36a9ad8e518lu979kex1j0ba5gaa0b6c3d6-44ef-49c3-a375-6bc4e7be6dea',
    'and_dcf063874d4316812096ed5535325704knelsacxtnryaf280fb0fe34-36a3-4fea-b53e-84bed6c6efa7',
    'and_36f8e4758f5dd9bd296d33d205460b84azrvzi5kgy9o9vuy2be94b49-cb31-4738-bc2a-01d09e3a6503',
    'and_f747fcd462a68e24cfff1572fbad13ff3tl0wmz0mab9om43842e7f6e-347e-4b70-a930-dc852e20d385',
    'and_ad7c534233ff26c05ca9d56652085f33q0xep1k1xugwwtct13429de8-3d2a-430e-8c08-4e73efd6546f',
    'and_0e62ecf7d73fb401e8a7efab2fad3053egepb2ml85xaliwn82def059-2cc3-4647-ad6a-cbbf3b67e0a3',
    'and_43faa24c936ea2cc7f630b5d1bbc619dhy331r0c2x08lpn919e9516e-ec43-4866-827e-11808c3e5e13',
    'and_4868aaa106021291de1a9daf79ad2d03vjtsiaqtny4olll1275bc0ac-2425-42c5-bbc7-a407370db3d4',
    'and_19c27d5556ee6717324729a4c9dc2796noofy9vx4kihjf4g06d409a3-1dc9-4ba3-b795-0a11d60b2b5c',
    'and_b8dde17e4b71dbe349f7dc440a72255f7spopjo3b2hgt2blebd15195-c2fb-44c1-aef5-d97c36e0a235',
    'and_28f08520c0c30176e677e9b645c926eenxhn8ombluzyv2cmb5b399fe-748c-424c-8d15-eef35efbc05f',
    'and_5d132cae0971b702c5ef44595a922948bzs0co1au089fdhh6af36913-245e-4559-8589-6893acc69f28',
    'and_3c4443fb100b9408a9b91feaaf579a3ek1cth5idxrqkhvyrc1735156-e1f6-481a-942f-3210dc54affd',
    'and_172b161e3f7349f0a223bcaa19c5d500z4bedprjllk6ulvr25857045-5408-44de-8382-1987feb9b172',
    'and_3e61c12bf3ebb66e81a72b9c5330b3689vvx98cvzlkg4qgjfc16e760-20d3-4f23-91c3-df4c72a5bb63',
    'and_a6621faddc08f214118acadc03cdeea3dmoh6z02wivh9kefabe9fde9-db6c-410b-8975-6d212da70b69',
    'and_3d6721cc3c12e7c76c9b9897f330f801a7fd92hjhw82pcqnbebd852e-9a73-40a1-8b04-8c9693c5d38d',
    'and_ff5744bde69f2206524b628f35fa7fd3hzsjxqeh6grt19b4a8ce23b7-27d8-4b25-ab80-b614d90c269f',
    'and_9cbe6a2396f52b188fab0a90ed3ca917x8ey84ur9xuvdxtcb156e38e-2391-4979-a847-d1dc6d1e9416',
    'and_59e4d772629c74c77966e60c61483898qg6nuf1h7j1a9bmy977c2414-2780-44d8-bd64-8cf46fa1963e',
    'and_958ffb48f4b228d02e3e4fef0d15e110f7pu2h8gh4jn11vbc709db3c-9fcc-40cd-ab5a-f7f06161c3ce',
    'and_f98c9edd344ef1f087619c1dd104f783rwvml98qq4weg45kb79b154d-b67a-4595-85d0-c0fc29d64587',
    'and_b62e8028809720857bb6dd54190ee05cz9i67usyx25ajc1y2a2a4b8f-efc1-423e-a0dd-5cb4d7bad621',
    'and_10c06f9ddb929e5d1e6b09a4f9743df1ya27w1ladxkawi4j20dc237a-019d-42d8-94ec-3628c1699ca6',
    'and_b81763502a51acd94be6c62133dbb206brp3c6762y48b7iaa0bfee72-b4ae-4e6b-89dc-c6ebfc226df1',
    'and_3c863c9527d44f421573994b8f1d151a04c1ab423b7845c09566f7bd-2654-44d5-9751-94b9f540ebd2',
    'and_35e9f99aaca40872b3d5b3c270569a1fd394a26c0813c313d3301e0b-c36f-44f1-8477-dcda08e06a27',
    'and_02d3ca3578f283529908905ab356e720gjvdx3w8nwy327ce26f87899-b885-4b7b-8381-7bcf0b87b647',
    'and_7cbfe8a818ceb4499b0122044a7e8b3aa160215d54f0aae6e22e7dd3-6e04-42d7-abe4-46c3b829448d',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf7e4aacf7447eafa77353e8b6-3c9d-480a-9b90-b16a73ed97b4',
    'and_cd9e459ea708a948d5c2f5a6ca8838cffaddccd5061fbfffcaff8ff6-cdf9-47da-8797-3afff4ff9e18',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf9dd39d3a99966dbb2871f78a-ef58-439b-854e-067bc3326ebe',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf9789806a49ddfcdebc12237d-e31d-4f22-9169-d973138f16a0',
    'and_63749f536752a6ebb8c4d6579b85a910b9129865a3e4520556780345-6923-472e-b67b-9cb32bcc163a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfbcc19abcbb9dbba045cd4123-41e8-4749-b1f9-5ff151828d4b',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf49e2f9ceaa28447ac1e92d70-a731-46cc-a5d9-a4932a98034b',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfbadb67cceb9074d16f8f2e6c-e993-4d6c-9b6d-6dd6b357f435',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf657fca3fea17b1f679e8d810-effe-407e-aae4-8d0c793fb87f',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfabbabf9cfaca30d13b562a92-0dd2-4287-ba27-75302eded572',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf32eb67e87b1f5cf87571e030-c1b7-479f-90af-212942e5abc4',
    'and_9fe7b9fe04c3300f79735132ca70def88d81e3608e17e95d1fd3a12d-aa03-4a21-be17-e50b4ab3235d',
    'and_cd9e459ea708a948d5c2f5a6ca8838cffa883e5bb95c423cafcad0b7-495d-43d3-a9b0-9e04bf0b8888',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfececa96b9238481cd14096d4-8ea5-467d-aae1-fbaebd657215',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfaa49f99b23f35ae770ceb380-189d-4baf-9277-0ca68a1097ad',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfbe97f07b8fcdcf5c367886dd-c847-4479-b183-853ccece9457',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe22caccd2a47cdef4c1687ee-46aa-46f8-a0d1-c4ad5197f8c3',
    'and_cd9e459ea708a948d5c2f5a6ca8838cff6deafabecaf0dbf453ab5da-4a51-4601-afe9-aa20a3bcdf0a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfaef7d67aca8d06b9458c58ee-e149-4bec-9c73-922f75b59f56',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfaca7fbe33894ddf02fb815c1-e188-4896-9186-7965a8b2df23',
    'and_5b69b45ed0b1269ec0e6622d82ec3885073e8742c6c4e999381012c9-66a1-485e-862f-a62bb4a6ecc2',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfae34f68159d6a7c0eca1283b-0c65-4700-9bf9-b1fc8a9a0139',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfa8255edef27f5cc5a0f4e000-64ac-44d3-bf59-641fa51277de',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfea53de9cfbb2b5fdb91ed781-d972-4421-b0f6-c9d041abfb8a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfad5bb9b2d8ce00fa961611cf-a8c4-42b3-a9b6-1a8e4de2c059',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfab5bd2bdbfbd48c96d9eb655-79d1-4361-b4ca-c869c16eb320',
    'and_cd9e459ea708a948d5c2f5a6ca8838cff1c4f7ca9a8cbefe6a879b38-ae53-4921-a53e-57be1c6fca64',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe3d3bce04780aff54d1d2839-39a0-4cc2-ac9b-dbb1e8a0847a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe1be02093f1737fee6e86220-b181-4d56-8d86-efc30a880e6c',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf914be7646bf33ffa75dbcc8a-ec64-47c5-9161-579b33633111',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe8d7eababcaf57fb15a35dee-8c93-4c89-9d24-ef0100a9479a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe50aceab4bc94fb2e88ad91c-0514-4207-99b9-b7bf9b687452',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfee308ccadd4cea7fce40005b-a8a4-47d0-a02a-1fb959ca6b9e',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfaaabcf5fe5524ea421b2d808-a11b-490b-b785-bb11b58455c9',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfe8abdf3cb5dcecada7a07c23-023c-4a40-a053-b1de5a4a4da2',
    'and_80f5179e4a62856da1a7cd397e2c9b753a05d69e10621391a7e74f1f-0f43-4ac5-afb8-146be5284ef9',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfef51e700d8f7d75bea678502-2f5b-4827-a5c8-9bdee96d762b',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf5553aa7a8bcbc44da4b4fe2d-4047-4a13-a458-73838139b71a',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfd495aaa63edae1c086208858-b826-4512-9e57-4fcf415adbef',
    'and_cd9e459ea708a948d5c2f5a6ca8838cf17541bcf6ddfaa78b0cd1ec7-58d9-4a42-808a-b50f3f540ed3',
    'and_21da01acc29254e32e97bc5c23d5285c6f26bfe7040ddf4dc27d7a10-1bfa-4ad9-88c6-77af66d2617b',
    'and_512e77a780f9cc0fb9002824e8495475ed92a8f3aa92cd505eaf4ba7-1faa-4ccf-bc4f-231465e2a413',
    'and_2821e7cd5d0c87ac30877d2c0fb9a21ca91b547a9495c07def8df077-f098-4a2a-a568-1a1c74161c65',
    'and_133b69dc5839138bdd779cb4f2d32988af15805e8321b92059cf440b-4c81-48e7-8738-a2e2b81746b2',
    'and_cd9e459ea708a948d5c2f5a6ca8838cffee2fa0de7102e99171edff2-c91c-417d-b033-4c1a3e2c3c73',
    'and_cd9e459ea708a948d5c2f5a6ca8838cfbd93ddde9209dad6083d4c6c-654a-47ef-b521-fb96a7ed7be2',
    'and_c29f2d7f882e5ad8d60b8b8df1c36b22a6de03203f4d875930d5d9eb-748c-4059-9004-fe26a9943bbc',
    'and_e5b11b6ea3fddbad0d38b7f99da7c759c4963ea275189cff87c568a5-ac88-484a-ab05-48d8252a9c7b',
    'and_4cdbf6eaaaab235a5aaf25d93ab750504e54cc171ec498f46110d280-6c2a-4fc7-a1c3-b06cbf0eeea4',
    'and_7cd6d0efc476c1efea7598f9e25213049a1e1dae597dac01cf7b08ec-d865-4452-a590-1de37ffced5a',
    'and_c5362f35f20fb064c81fe63dfa4376eed36e0259433f70c3697107bf-5d4c-4554-85f0-9712522b086b',
    'and_b74eada9d33ca550be5c4f794eebd027945ddd997fd247e266916d9f-217a-4bdb-b171-f00fe203b26c',
    'and_56300f0d894f482ba0d846abcb3d6c7b1a2e4244c57d33181cae35ab-65bd-4137-b30e-a0d2fbc1c2aa',
    'and_09925734b592905063ce48280f31c33bc9af17ab9d1327853317531a-e2d3-4eaa-a4d9-9f480ce3e2f3',
    'and_0e300e153f24d15fedff2592f6aa19684da5675bc877e3af5a552b10-0ef3-4ebf-ac5c-61dbdac10ff2',
    'and_e16ff9c02ed7685ed1fd6673251405caa7797d9f75e0656a1003fcc2-4fe0-49aa-bdf9-e691cc325f14',
    'and_144cf3f1801b0ab21cca069e05a5fe9d48d5236e66e22957a64ca8cc-a0ac-40b3-a6ea-632cf60107cd',
    'and_9b7ae38b08260486bdccac22eed02c223bc8b729a2b03ecbe1e4bc7a-135f-4647-b9f8-54614bb30c73',
    'and_723f0ca97306d009a9454261650188ab76ea83c0e0554f6ee8e06b4b-5d27-456c-a663-1a1a7e3f2f6e',
    'and_592ac36ab669673780396ad9583cae5328e2aab7b96e6806a572bba0-e2cb-4adf-8e60-05ccb5272a50',
    'and_bfc98d96024decf2bb76acf9b0b6c677b4311a292f942d791a512bb4-d412-40ab-87d3-657dcefbd3aa',
    'and_f3a995cbe185a8e30726db9a695bbfdf2d7952a3246cb38db5521d71-622e-4c2e-bfc4-2ed8583cc544',
    'and_b3f0cf7b109edaf989ffea5c238682abe2f4127e03f02c0dc8ed14a0-8c70-4d7e-a5d7-0b6514ec7ff5',
    'and_428e68541f70886cf65c17e9af260fed659c503b232319393023370d-6b7d-480c-a2a3-26e9b663b05e',
    'and_5a0a114df0b56924e78799596ca7368eec303a552d2729e8aa3a44ea-3512-4abd-8479-d2b09c4dd982',
    'and_11c9eab482a239ca7129cdc10d65cd5e5c28342b1eb65e1be581ba33-41ca-4ecb-97b5-76438c5962b8',
    'and_4f90e1ef25df4e1d30b5b94b4d931214d0260d6237ac8ca30ff59225-fadd-4902-8a78-4d85d377d8b8',
    'and_f5995869aa0e170ed24148d2143ad36b9f155b5690a6259115663878-2457-4903-8229-8655635e4ee2',
    'and_beaf98bc5a282e8bb27eda44d0260b9f4d709a960dde37e97d209435-ef58-498e-ace1-891580f8fe56',
    'and_6e4cc3036d6bd91462f0eba9b86afc891c37fd2a9a59c2746795fc50-f6ae-4d62-9055-ccae66df7cb4',
    'and_7f16180705371e57e58f32e164ca41d840c25da8af9656571209a63f-ff12-4e50-98e9-cc1833bdb4be',
    'and_81fe1e532f2d8554efcfaa67e45e46bc45388590908526fb1310b8a5-bfcb-4f71-8cdd-83a884ddb4e1',
    'and_64334b60a5f3fc48236902079dea8b63722df5f91e080584fc114055-7070-463d-ad20-ad3153c9471f',
    'and_2c289141d3ae6a4d12abe63b1562e7fda87b4ecfc7ee5b21b8d5c489-f2cb-45c7-87c2-7c9f2121d08d',
    'and_22f64a81761793408dd59b98fbd56d1460f79c87351409f5f9cbf758-80ff-4d3e-83f4-0893c81aa828',
    'and_d1be17c7d2f4bbb443e9ba18ce4cace32eb4e678435075240ffb4001-06dc-45e6-b8f5-937c29b01b53',
    'and_66b3bf6cf1bedc16bca2e31e8687d3a85d1c5a95afc2aeb15281dd59-9e7b-4eb5-927f-c571fe0a8ce1',
    'and_2e710960fb8968a5ba02eeb3780eff1c56475488e218d9f876ab9b68-e386-49f1-9f14-dae2dba21de8',
    'and_d7cbf7fc1adeb434e3d2af584e5463bb4d6b0d8abfde2a52d940d62a-0a70-4d7e-ad76-6532d08ddae1',
    'and_e5d97d0581c73525fb2dbcd8ce7761fc55444f48fa5c617ed46daa1c-ada3-41fb-a973-75bdd354473b',
    'and_b68a3f42a08415a11ef14a87d4a135a3aa9139f1c54f6f719ca44199-4622-4d2c-9228-7039ed0e1663',
    'and_da4efde6916a3c073c550bba786658368599dd28edb016a8a0f4849d-cfbe-4c1c-832c-18fd9393840e',
    'and_23a974e50f4e226d3b577913a5058202e8a8890ab5394022094b8b74-9e64-4faa-9f9f-eb1896e8566b',
    'and_6662f7c9cae5e46b36e65d60ff718726697e68e95a5b98ddcfbf923c-990f-4141-85cf-4645f672fb20',
    'and_44442c51622eee9bbc0f8cd724d2bb7ae4527406d17886bdf6f87b73-f5f8-4798-8314-e08b10cea639',
    'and_53889a87e8862e766e63ac6df5f88c546bdcb16a1adea59b26993125-a3f6-4db9-b9c0-84198ee97a6c',
    'and_a297e31378932914cbf3ffbdbb363aad85cc8db44c0f55fd8d8d5ec3-7ff5-46db-a895-9ef552d4ae24',
    'and_9b277c9ae517b7fcf351aa79152e8e80979c56b914862bfd9dd5b775-5f11-494e-91e9-30b1add6976d',
    'and_1762aaa34bfc2fd4dce15aee2939453bc5a0ccebc7813aa8f917f54c-174d-414a-8b78-f03c577c709a',
    'and_9283dfe78c7578b3926bb5aba4434d7f617944de8df5a4fdb697d358-d8e9-4503-a6a3-bcd16a402f9e',
    'and_4b94914cf11b449cfd60966623736934c7ee65a4f2727fdb34d61723-8259-4ae9-b76e-ba705613a762',
    'and_55afb283ac1290e1149a396f25616df6f77eb1de29d19e52ae02597e-5f16-4061-96a4-d45be21a7ca1',
    'and_06ec9a584538c77eeb09ef5f5074f48d482789716619f7c4bd3ea5f1-af3e-4278-8cbd-69ca7400923f',
    'and_c811e5d265be988b2345c7c7fc5121c91b447d5bcb485a7f8e093762-b51e-4b11-9f67-a0b1b831c6f2',
    'and_f4a1007cbc9654bbc1166b49fcaf8ab54138d4ef55ded512e813e994-ff6f-453c-a52d-f9e35e714eaf',
    'and_612ff956b07521a41de243ec73036f81b318696c5c10405c043c2221-4ba1-4c0b-9ed1-1e702d7baef6',
    'and_767ba225bb421dca4150ec07b377f7737a5734760849663e6e9abfd1-c661-425e-b873-61f3a6503b82',
    'and_4fe58bf1dea708000ccebb2b035893caad72c8d494b08f0cf0c8d1ed-54e2-43a0-a791-e9d4b6dabe50',
    'and_68b28b784823e3010ba262b3125a1019983c619a050fe83f19084fb8-debe-462b-a168-2fd57aadce77',
    'and_4110102db68ff9b8d10e0b45ac32e30cc95fcc4c95ac9c52b384c5b4-f0ed-45cf-89b3-da3a3af385cf',
    'and_569ea29e46ddc92a74a9285103951314684dcb386997bdb780761423-8bba-4116-894a-060b594fd393',
    'and_b91181c1d82aa413d063845a345454b1349403edfc553efa4c7d7aa5-b953-4ce6-b87e-c40eff2ad63c',
    'and_4afa36077b70d1b69385adc7f5841af226492c814b3ca6679151f1ef-2775-49ec-ae63-19de3b09d6bf',
    'and_31eab46ea415e0dfe19fc4e655a15ea3445569080659fca99c9b31ed-ca7b-4453-a7fc-708a443add46',
    'and_ef8deb8ce24578915bfe254b5855695e3743bd882b1b1fedf3ad118f-4408-45ff-b895-447fc6c27d87',
    'and_3c03534ad2b0c2a119133b8b23ece8fac39797c3dbc9ab11d0542fe8-e3bb-4fab-8a98-313b23e87e79',
    'and_5a63032c300802bb9d4cbeb97aade4e10ef52d19c444650859e616e7-269e-4876-b628-4ac0d6928d19',
    'and_9024b1e36beb568954821f7ecfe8b59f37cfad4c10a466cee584d151-1f68-4a58-a7bf-70b98cc58bd7',
    'and_21734aa11933e49af91553b42971b66434f252b6845c8ca5aa67f36d-96d5-4d08-a695-b51d1a69c91f',
    'and_a744ee2497e4a3ccfe1c4b87ee87a2d269275c2cbb16ec7a6c7ee839-b5bd-45dc-a830-9a9f5a082740',
    'and_71dbc08ba43fa02d29c0c830afb8d3aaf9b044a6be9542a7b3c8d245-12c8-4491-a4c4-af2be1a3ec0f',
    'and_d4ebcc6584749356a6d7a993b05fa1222e973ea52d28ec31b1d9381a-0b96-46bd-9c0a-ba0eba78b884',
    'and_43df6dd9f3c5c35c9f1702ac89386e23911fedb430ea8042e37f47ec-4dbc-45d8-9bcc-fea5e947b6b1',
    'and_e69deafd9459332686da747f5842de4d8c455fec0172d3462c79a939-ab70-49a2-918c-137ea1c1f258',
    'and_1ba80df5b3cc9c09fe8f6ed0aad55d6e37c9b852511a5d49c255f468-50a2-421e-9c27-b82dd8351a12',
    'and_df91a9c09f0550384e0bc706a3294688cf2bcb6a143507248a79cb15-ce28-44aa-af14-78b5cffe0b4e',
    'and_086f1a4d6b8d162176bd1542f8441b3fb7bf5310a9ec65f317e25dca-c653-4bf5-b1c3-b1328de5edca',
    'and_267540f38448e93474e00fbf08e37110a24c7001f6c01f594567f3ee-d565-4bcd-96f8-1d00fe5b53a7',
    'and_9669b6d80e076a932f15c8360430f8d963fc4888714923476a43b0e7-f98e-4063-bee5-aed8e4c9ed8a',
    'and_0eb413d00ee1fc463951d94e0a1a3bcecc40e43877bdd0dd0b0a1f5e-a9ad-4ebc-b7ad-ba8ce591f1a2',
    'and_bc91786f46a576cf003da38493f5616dbde258b2f063e8b921574343-4c19-42d8-837f-4d42efaed8cf',
    'and_2fac430913ef971cff0413d40b98950fafs8vn7qf53wt1m389efed44-5a38-4ce4-9744-c59efc3c12be',
    'and_c9dde76504f5b43f14da13e79452fb42c25956822d831d12eedc04ef-c928-4f76-b443-0aa6fc1b09f9',
    'and_46230fab076e8e9d30a833f4ef9d1e06gwzluqxjevgfrq22e813061d-8ed3-4518-b4b7-d1abe0f2425d',
    'and_11971f069982e866d75bd30a665e8fc173616cca898231f77492501e-4b3b-4f9f-aae4-9107bb768b16',
    'and_823f4da815571fbaf59844df64b42c672e05dddd0b0d9c3393a61ffc-031a-4af9-b89e-357e13ba9b6f',
    'and_826858d0527509592fa80a80ff614a44o6ljtt5tzs3x2b076656bdf7-0e3a-499a-8e5a-5b4c59090c6e',
    'and_4e4340f9df25caa95364073a55bdbab31cb5923e366b223c3bd73ce5-7e6d-41dd-bb7c-2d8950644f29',
    'and_23a98011c21cb22f87425618a1410e83ufj7vjoztmgiy4hn99c77d99-981e-4274-a2fc-ba78cd79705f',
    'and_26cf255530f535fd3a1d40aceb01757clkqejye8shs1rzsg1e42f532-f5bf-46fe-bfec-3bdd1256111e',
    'and_c3028cb76a4833266c0f312eea1e154cftjs7kkphwynxmexa2afa38a-679d-4ebd-8301-72f6f6f4e17e',
    'and_014511d705e25ee69d08334dc561c302afmx0pi943gw9y4c2be28162-075e-4cb2-b7af-dc94451b83ca',
    'and_7ac8a22d4997f195af6b0fd733859fb3ik0uy0ziydxvejo9913e9d11-57fa-4bc4-979e-93cd3d377893',
    'and_92e7311dee445c53d4c5f2d15b9e3a3b1622awi7dh4cvz4p17668c41-243e-464f-b69e-5455c8cf4b8e',
    'and_b36fda33acfa5a7e2821baf240494e7dse1yx80g1cdkzliud52225d8-5b4d-4e92-9690-47c3585874ba',
    'and_df88ca5e730338b82bb41649dd3e212ey2ullg9gviexwgtda373a9e6-3b60-4f55-945a-964e3d24f3b0',
    'and_6549ffc380a009bcd9ceaefa824ecffeyk8qc7mz7tpurmyvf72a6705-34b5-4aae-b3b2-930eb4f866f9',
    'and_f6cc7fb8578678369336b81a4da8c264pqig6bwua7u87bax7d60e684-d3fe-41bb-86ce-d8e2ea7d6ba3',
    'and_814bceefc76022f711fee9148c4a67576xdjrncqx3itco3l23c53a38-8ec4-4393-a4d3-7098c36f882e',
]

DEVICE_MODELS = [
    'Xiaomi:23049PCD8G', 'Xiaomi:2201123G', 'Xiaomi:22011211C', 'Xiaomi:2211133C', 'Xiaomi:23078PND5G', 'Xiaomi:22101316G',
    'Xiaomi:Redmi Note 12', 'Xiaomi:Redmi Note 12 Pro', 'Xiaomi:Redmi Note 11', 'Xiaomi:Redmi 12C', 'Xiaomi:Redmi 10', 'Xiaomi:Mi 11',
    'Xiaomi:Mi 11 Ultra', 'Xiaomi:23013RK75G', 'Xiaomi:2304FPN6DG', 'Xiaomi:23054RA19I', 'Xiaomi:22071219CG', 'Xiaomi:2206123SC',
]


def setup_logger():
    logger = logging.getLogger('ML')
    logger.setLevel(logging.ERROR)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[ML] %(message)s'))
    logger.addHandler(handler)
    return logger


logger = setup_logger()


def load_device_ids():
    if not DEVICE_IDS:
        return ['ios_D08FE22A-7074-4DEB-BC67-78EEA4FD11B6_1714741163095700']
    return DEVICE_IDS.copy()


def load_device_models():
    if not DEVICE_MODELS:
        return ['Xiaomi:Redmi Note 12']
    return DEVICE_MODELS.copy()


def remove_failed_device_id(failed_device_id):
    global DEVICE_IDS
    if failed_device_id in DEVICE_IDS:
        DEVICE_IDS.remove(failed_device_id)
        return True
    else:
        return False


AES_KEY = bytes.fromhex('f5a193d50ade553e9835595f5cd75ddd')
AES_IV = b'\x00' * 16


class BaseConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sequence = 1
        self.socket = None
        self.queue_data = b''
        self.last_header_size = 0
        self.ban_seen = False
        self.ban_info = {}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.socket.settimeout(2)

    def cleanup(self):
        if self.socket:
            self.socket.close()
            self.sequence = 1
            self.socket = None

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

    def send_data(self, id, sdp):
        packet = SdpStruct({0: id, 1: self.sequence, 5: sdp.data}).data
        buf = zstd.compress(packet)
        flags = (len(buf) + 4) | (16 << 24)
        buf = flags.to_bytes(4, 'big') + buf
        dbg(f"SEND  packet_id={id}  seq={self.sequence}  payload_bytes={len(sdp.data)}  compressed={len(buf)}")
        dbg(f"      SDP fields", dict(sdp))
        self.socket.send(buf)
        self.sequence += 1

    def recv_data(self):
        try:
            while len(self.queue_data) < 4:
                data = self.socket.recv(4096)
                if not data:
                    return None, None
                self.queue_data += data
            flags = int.from_bytes(self.queue_data[:4], 'big')
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
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                if len(data) % 16 != 0:
                    data = cipher.decrypt(data[:-1])
                else:
                    data = cipher.decrypt(data)
                data = data.rstrip(b'\x00')
            elif compression_type == 3:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                if len(data) % 16 != 0:
                    data = cipher.decrypt(data[:-1])
                else:
                    data = cipher.decrypt(data)
                data = data.rstrip(b'\x00')
                data = zlib.decompress(data)
            elif compression_type == 18:
                cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=AES_IV)
                if len(data) % 16 != 0:
                    decrypted_data = cipher.decrypt(data[:-1])
                else:
                    decrypted_data = cipher.decrypt(data)
                data = zstd.decompress(decrypted_data.rstrip(b'\x00'))
            result = SdpStruct(data)
            id = result[0]
            if id is None:
                dbg("RECV  id=None — dropped")
                return None, None
            res = result.get(6, None)
            if not res or not isinstance(res, bytes):
                res = result.get(5, None)
                if not res or not isinstance(res, bytes):
                    # still sniff outer envelope (stub packets are ignored
                    # inside inspect_ban via _looks_like_player)
                    try:
                        self._sniff(result)
                    except Exception:
                        pass
                    dbg(f"RECV  id={id}  body=<empty>", color=Fore.YELLOW)
                    return id, None
            parsed_res = SdpStruct(res)
            try:
                self._sniff(parsed_res)
            except Exception:
                pass
            try:
                self._sniff(result)
            except Exception:
                pass
            dbg(f"RECV  id={id}  body_bytes={len(res)}  compression_type={compression_type}", color=Fore.CYAN)
            dbg(f"      SDP fields", dict(parsed_res), color=Fore.CYAN)
            return id, parsed_res
        except socket.timeout:
            return -1, None
        except Exception:
            return None, None


class GameConnection(BaseConnection):
    def __init__(self, device_id, device_model=None):
        super().__init__('login.ml.youngjoygame.com', 30021)
        self.device_id = device_id
        self.device_model = device_model or "Xiaomi:Redmi Note 12"
        parts = self.device_id.split('_')
        if len(parts) >= 2:
            device_info = parts[1]
            if len(parts) >= 3 and len(device_info) < 32:
                device_info = device_info + "_" + parts[2]
            if len(device_info) >= 32:
                self.imei_md5 = device_info[:32]
                if len(device_info) >= 48:
                    self.android_id = device_info[32:48]
                    if len(device_info) > 48:
                        self.advertising_id = device_info[48:]
                    else:
                        self.advertising_id = ""
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
        self.channel = 'and_usa'
        self.client_version = '2.2.16.1232.1'
        self.account_id = 0
        self.session_key = ''
        self.zone_id = 0
        self.game_server_host = ''
        self.game_server_port = 0
        self.creation_ts = 0

    def login_to_login_server(self):
        if self.host != 'login.ml.youngjoygame.com' or self.port != 30021:
            self.cleanup()
            self.host = 'login.ml.youngjoygame.com'
            self.port = 30021
            self.connect()
        dbg(f"LOGIN SERVER → sending packet 1  device_id={self.device_id[:30]}...")
        self.send_data(1, SdpStruct({
            0: self.device_id,
            1: f'gps_adid={self.advertising_id}&android_id={self.android_id}&device_unique_id={self.imei_md5}',
            2: self.client_version,
            3: self.channel,
            4: 'en'
        }))
        id, res = self.recv_data()
        dbg(f"LOGIN SERVER ← response id={id}")
        if id == 2 and res:
            self.account_id = res.get(0)
            self.session_key = res[1]
            self.zone_id = res[2][0]
            self.creation_ts = res.get(19, 0)
            dbg(f"LOGIN OK  account_id={self.account_id}  zone_id={self.zone_id}  session_key={str(self.session_key)[:20]}...  creation_ts={self.creation_ts}", color=Fore.GREEN)
            return True
        else:
            dbg(f"LOGIN FAILED  id={id}  res={res}", color=Fore.RED)
            return False

    def get_game_server(self):
        dbg(f"GAME SERVER → sending packet 5  account_id={self.account_id}")
        self.send_data(5, SdpStruct({
            0: self.account_id,
            1: self.session_key,
            2: self.client_version,
            5: self.zone_id,
            6: self.channel
        }))
        id, res = self.recv_data()
        dbg(f"GAME SERVER ← response id={id}")
        if id == 6 and res:
            game_server = res[1]
            self.game_server_host, self.game_server_port = game_server.split(':')
            self.game_server_port = int(self.game_server_port)
            dbg(f"GAME SERVER OK  host={self.game_server_host}  port={self.game_server_port}", color=Fore.GREEN)
            return True
        else:
            dbg(f"GAME SERVER FAILED  id={id}", color=Fore.RED)
            return False

    def connect_to_game_server(self):
        self.cleanup()
        self.host = self.game_server_host
        self.port = self.game_server_port
        self.connect()
        dbg(f"GAME CONN → sending handshake 10001 + 10101  account_id={self.account_id}  zone_id={self.zone_id}")
        self.send_data(10001, SdpStruct({
            0: self.account_id,
            1: self.session_key,
            2: self.zone_id,
            4: self.client_version,
            13: self.channel,
            15: self.device_id
        }))
        self.send_data(10101, SdpStruct({0: 0, 2: 2}))
        while True:
            id, res = self.recv_data()
            if id is None:
                dbg("GAME CONN ← id=None  aborting", color=Fore.RED)
                return False
            elif id == 10002:
                dbg("GAME CONN ← 10002  connected OK", color=Fore.GREEN)
                return True
            elif id == -1:
                dbg("GAME CONN ← timeout", color=Fore.RED)
                return False
            else:
                dbg(f"GAME CONN ← unexpected id={id}  (waiting for 10002...)", color=Fore.YELLOW)
        return False

    def lookup_player(self, search_value, search_type="id", server_filter=None):
        if search_type == "id":
            lookup_data = SdpStruct({1: int(search_value)})
        else:
            lookup_data = SdpStruct({0: str(search_value).strip()})
        dbg(f"LOOKUP → packet 11153  type={search_type}  value={search_value}  server_filter={server_filter}")
        self.send_data(11153, lookup_data)
        id_20001_count = 0
        while True:
            id, res = self.recv_data()
            if id is None:
                dbg("LOOKUP ← id=None", color=Fore.RED)
                return None
            elif id == -1:
                dbg("LOOKUP ← timeout", color=Fore.RED)
                return None
            elif id == 11154:
                dbg(f"LOOKUP ← 11154  RESULT RECEIVED", color=Fore.GREEN)
                if search_type == "nickname" and server_filter is not None:
                    filtered_result = self.filter_by_server(res, server_filter)
                    dbg(f"LOOKUP filter_by_server={server_filter}  matched={filtered_result is not None}", color=Fore.GREEN)
                    return filtered_result
                else:
                    return res
            elif id == 20001:
                id_20001_count += 1
                dbg(f"LOOKUP ← 20001  (interim/keep-alive #{id_20001_count}  header_size={self.last_header_size})", color=Fore.YELLOW)
                if self.last_header_size < 100 and id_20001_count >= 2:
                    dbg("LOOKUP ← 20001 x2 small  → player not found", color=Fore.RED)
                    return None
            else:
                dbg(f"LOOKUP ← unexpected id={id}", color=Fore.YELLOW)

    def get_role_info(self, role_id, zone_id):
        try:
            dbg(f'ROLE INFO -> packet 10128  role_id={role_id}  zone_id={zone_id}')
            self.send_data(10128, SdpStruct({1: int(role_id), 2: int(zone_id)}))
            best_res = None
            for _ in range(30):
                id, res = self.recv_data()
                if id is None:
                    dbg('ROLE INFO <- connection closed', color=Fore.RED)
                    break
                elif id == -1:
                    dbg('ROLE INFO <- socket timeout', color=Fore.YELLOW)
                    break
                elif id == 20001:
                    dbg(f'ROLE INFO <- 20001 keep-alive — skipping', color=Fore.YELLOW)
                    continue
                elif id == 10129:
                    dbg(f'ROLE INFO <- 10129  raw_fields={dict(res) if res else {}}', color=Fore.GREEN)
                    if res is None:
                        continue
                    if best_res is None:
                        best_res = res
                    if res.get(9, 0) > 0:
                        return res
                    continue
                else:
                    dbg(f'ROLE INFO <- id={id} (unexpected, skipping)', color=Fore.YELLOW)
                    continue
            if best_res is not None:
                dbg(f'ROLE INFO <- returning best response', color=Fore.GREEN)
                return best_res
            dbg('ROLE INFO <- no response received', color=Fore.RED)
            return None
        except Exception as e:
            dbg(f'ROLE INFO error: {e}', color=Fore.RED)
            return None

    def get_skin_role_info(self, role_id, zone_id, max_retries=3):
        for attempt in range(max_retries):
            try:
                dbg(f'SKIN ROLE INFO -> packet 10143  role_id={role_id}  zone_id={zone_id}')
                self.send_data(10143, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                max_timeouts = 3
                while timeout_count < max_timeouts:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid == 10144:
                        dbg(f'SKIN ROLE INFO <- 10144  tags={list(dict(res).keys())[:20] if res else []}', color=Fore.GREEN)
                        return res
                    elif pid == 20001:
                        continue
                    else:
                        continue
            except Exception as e:
                dbg(f'SKIN ROLE INFO error: {e}', color=Fore.RED)
        return None

    def get_v2l_status(self, role_id, zone_id, max_retries=2):
        for attempt in range(max_retries):
            try:
                dbg(f'V2L STATUS -> packet 10208  role_id={role_id}  zone_id={zone_id}')
                self.send_data(10208, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                max_timeouts = 2
                while timeout_count < max_timeouts:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid == 10208:
                        dbg(f'V2L STATUS <- 10208  tags={list(dict(res).keys())[:20] if res else []}', color=Fore.GREEN)
                        if res is not None:
                            return {"_source": 10208, "_data": dict(res)}
                    elif pid == 20001:
                        continue
                dbg(f'V2L STATUS -> packet 10145 (fallback)  role_id={role_id}  zone_id={zone_id}')
                self.send_data(10145, SdpStruct({0: int(role_id), 1: int(zone_id)}))
                timeout_count = 0
                while timeout_count < max_timeouts:
                    pid, res = self.recv_data()
                    if pid is None:
                        break
                    elif pid == -1:
                        timeout_count += 1
                    elif pid in (10146, 10160):
                        dbg(f'V2L STATUS <- {pid}  tags={list(dict(res).keys())[:20] if res else []}', color=Fore.GREEN)
                        if res is not None:
                            return {"_source": pid, "_data": dict(res)}
                    elif pid == 20001:
                        continue
            except Exception as e:
                dbg(f'V2L STATUS error: {e}', color=Fore.RED)
        return None

    def filter_by_server(self, result, target_server):
        if not result or not result.get(0):
            return None
        players_list = result[0]
        for player in players_list:
            if isinstance(player, dict):
                player_server = player.get(1)
                if player_server == target_server:
                    filtered_result = {0: [player]}
                    return filtered_result
        return None

    def _banned_player_data(self, base_result=None, role_info=None,
                            v2l_data=None):
        info = self.ban_info or {}
        player = None
        if base_result is not None:
            try:
                player = extract_player_data(
                    base_result,
                    role_info=role_info,
                    creation_ts=self.creation_ts,
                    v2l_data=v2l_data,
                    ban_info=info,
                )
            except Exception:
                player = None
        if player is None:
            player = {
                'nickname': None,
                'level': 0,
                'current_rank': 'Unknown',
                'high_rank': 'Unknown',
                'skin_count': 0,
                'hero_count': 0,
                'collector_tier': 'No Tier',
                'collector_point': 0,
                'skin_breakdown': {},
                'hero_history': [],
                'last_heroes_purchase': [],
                'emblem_levels': [],
                'skin_history': [],
                'last_match': None,
            }
        player['ban_status'] = 'BANNED'
        code = info.get('ban_code')
        reason = info.get('reason_name')
        if code or reason:
            player['ban_code']   = code or '21'
            player['ban_reason'] = reason or BAN_REASONS.get(
                player['ban_code'],
                'Using Plug-in Apps to Compromise Competitive Fairness')
        else:
            player['ban_code']   = None
            player['ban_reason'] = None
        player['ban_duration'] = format_ban_duration(info)
        return player

    def __enter__(self):
        super().__enter__()
        if not self.login_to_login_server():
            raise ConnectionError("LOGIN_FAILED")
        if not self.get_game_server():
            raise ConnectionError("SERVER_SELECTION_FAILED")
        return self


def format_timestamp(timestamp):
    try:
        utc_dt = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
        pht_dt = utc_dt + datetime.timedelta(hours=8)
        pht_date_str = pht_dt.strftime("%Y-%m-%d %H:%M")
        now_pht = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
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
    except:
        return "Invalid timestamp"


def format_timestamp_full(timestamp):
    try:
        utc_dt = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
        pht_dt = utc_dt + datetime.timedelta(hours=8)
        return pht_dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Invalid timestamp"


def parse_skin_counts(tag_118):
    if not tag_118 or not isinstance(tag_118, dict):
        return {}
    skin_data = None
    for k in (4, '4'):
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


def extract_player_data(result, role_info=None, creation_ts=0, v2l_data=None,
                        ban_info=None):
    if not result or not result[0] or len(result[0]) == 0:
        return None
    try:
        player_data = result[0][0]
        nickname = player_data.get(2, "Unknown")
        player_id = player_data.get(0, "Unknown")
        server = player_data.get(1, "Unknown")
        level = player_data.get(3, "Unknown")
        skin = player_data.get(83, "Unknown")
        hero_count  = player_data.get(4, 0)
        matches     = player_data.get(17, 0)
        rating_score   = player_data.get(9, 0)
        if role_info:
            hero_count = role_info.get(9, hero_count)
            matches    = role_info.get(22, matches)
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
        if squad_id:
            squad_id_display = f"Squad ID: {squad_id}"
        else:
            squad_id_display = "N/A"

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
                        val = int(_v)
                        v2l_status = "Enabled" if val > 0 else "Disabled"
                        break
                    except (ValueError, TypeError):
                        pass

        followers = 0
        if role_info and isinstance(role_info, dict):
            followers = role_info.get(23, 0)
        if not followers:
            followers = player_data.get(15, 0)

        popularity = player_data.get(14, 0)
        bio = player_data.get(24, "").strip() if isinstance(player_data.get(24), str) else ""

        likes = 0
        if role_info and isinstance(role_info, dict):
            likes = role_info.get(24, 0)
        if not likes:
            likes = player_data.get(61, 0)

        credits_score = "N/A"
        _cs_val = 0
        if role_info and isinstance(role_info, dict):
            _cs_val = role_info.get(20, 0)
        if _cs_val and isinstance(_cs_val, int) and _cs_val > 0:
            credits_score = f"{_cs_val}/110"
        else:
            _cs_fb = player_data.get(80, 0)
            if _cs_fb and isinstance(_cs_fb, int) and _cs_fb > 0:
                credits_score = f"{_cs_fb}/110"

        restriction_flags = "None"
        _t117 = None
        if role_info and isinstance(role_info, dict):
            _t117 = role_info.get(117)
        if _t117 is None:
            _t117 = player_data.get(117)
        if _t117 is not None:
            if isinstance(_t117, dict):
                _raw = _t117.get(0, 0)
            else:
                try:
                    _raw = int(_t117)
                except:
                    _raw = 0
            _flag_count = int(_raw) + 1
            _total_bits = 7
            _pct = round((_flag_count / _total_bits) * 100, 1)
            if _pct < 30:
                _risk, _risk_icon = "Low Risk", "✅"
            elif _pct < 60:
                _risk, _risk_icon = "Medium Risk", "⚠️"
            else:
                _risk, _risk_icon = "High Risk", "🚨"
            restriction_flags = f"{_pct}% {_risk_icon} ({_risk})"

        _t135 = player_data.get(135, {})
        _aff_level = _t135.get(1, 0) if isinstance(_t135, dict) else 0
        _AFFINITY_MAP = {0:"None", 1:"Bronze", 2:"Silver", 3:"Gold", 4:"Platinum", 5:"Diamond"}
        _aff_tier = _AFFINITY_MAP.get(_aff_level, f"Level {_aff_level}") if _aff_level else "None"
        _aff_names = []
        if role_info and isinstance(role_info, dict):
            _tag82 = role_info.get(82, [])
            if isinstance(_tag82, list):
                for _entry in _tag82:
                    if isinstance(_entry, dict):
                        _aff_name = _entry.get(2, "")
                        if _aff_name and isinstance(_aff_name, str):
                            _aff_names.append(_aff_name)
        affinity_label = ', '.join(_aff_names) if _aff_names else _aff_tier

        _skin_ts = player_data.get(176, 0)
        if not _skin_ts and isinstance(role_info, dict):
            _skin_ts = role_info.get(176, 0)
        if _skin_ts and isinstance(_skin_ts, int) and _skin_ts > 100000000:
            latest_skin_date = format_timestamp(_skin_ts)
        else:
            latest_skin_date = "N/A"

        _latest_skin_id = player_data.get(175, 0)
        if not _latest_skin_id and isinstance(role_info, dict):
            _latest_skin_id = role_info.get(175, 0)

        if _latest_skin_id:
            _tier_from_db = get_skin_tier(_latest_skin_id)
            if _tier_from_db:
                latest_skin_tier = _tier_from_db
                _tier_label = _tier_from_db
            else:
                latest_skin_tier = "Unknown"
                _tier_label = "Unknown"
            latest_skin_id_str = f"{_latest_skin_id} ({_tier_label})"
        else:
            latest_skin_id_str = "N/A"
            latest_skin_tier = None

        import time as _time
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
            starlight_user = "Yes ⭐" if _sl_expiry > _time.time() else "No"
            starlight_expiry = format_timestamp(_sl_expiry)
        else:
            starlight_user = "No"
            starlight_expiry = "N/A"

        starlight_months = player_data.get(60, 0)
        tickets = 0
        if role_info and isinstance(role_info, dict):
            tickets = role_info.get(49, 0)
        if not tickets:
            tickets = player_data.get(49, 0)
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
            _now_utc = datetime.datetime.now(datetime.timezone.utc)
            _create_dt = datetime.datetime.fromtimestamp(_age_ts, datetime.timezone.utc)
            _age_delta = _now_utc - _create_dt
            _age_years = _age_delta.days // 365
            _age_months = (_age_delta.days % 365) // 30
            _age_days_rem = _age_delta.days % 30
            if _age_years > 0:
                account_age = f"{_age_years}y {_age_months}m {_age_days_rem}d"
            elif _age_months > 0:
                account_age = f"{_age_months}m {_age_days_rem}d"
            else:
                account_age = f"{_age_delta.days}d"

        _tag45 = player_data.get(45, {})
        if not _tag45 and isinstance(role_info, dict):
            _tag45 = role_info.get(45, {})
        last_heroes_purchase = "N/A"
        if isinstance(_tag45, dict) and _tag45:
            _hero_entries = []
            for _entry in _tag45.values():
                if isinstance(_entry, dict):
                    _hid = _entry.get(0, 0)
                    _hts = _entry.get(1, 0)
                    _hname = HERO_ID_MAP.get(_hid, f"Unknown({_hid})")
                    _hero_entries.append((_hts, _hname))
            _hero_entries.sort(key=lambda x: x[0], reverse=True)
            if _hero_entries:
                last_heroes_purchase = ", ".join(h for _, h in _hero_entries)

        mcl_wins = 0
        if role_info and isinstance(role_info, dict):
            mcl_wins = role_info.get(46, 0)
        if not mcl_wins:
            mcl_wins = player_data.get(104, player_data.get(103, 0))

        win_count = 0
        if role_info and isinstance(role_info, dict):
            win_count = role_info.get(22, 0)
        total_battles = 0
        if role_info and isinstance(role_info, dict):
            total_battles = role_info.get(77, 0)
        if not total_battles:
            total_battles = player_data.get(17, 0)
        _wins_for_rate = win_count if win_count else total_wins
        if total_battles > 0 and _wins_for_rate > 0:
            _wr_val = (_wins_for_rate / total_battles) * 100
            win_rate = f"{min(_wr_val, 100):.1f}% (approx)" if _wr_val > 100 else f"{_wr_val:.1f}%"
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
            _currency_raw = role_info.get(111, None)
            if isinstance(_currency_raw, dict):
                diamonds = int(_currency_raw.get(0, 0) or 0)
                bp       = int(_currency_raw.get(1, 0) or 0)
            elif isinstance(_currency_raw, int):
                diamonds = int(_currency_raw or 0)
        if not bp:
            bp = int(player_data.get(83, 0) or 0)

        _diamond_buy_ts = player_data.get(42, 0)
        if _diamond_buy_ts and isinstance(_diamond_buy_ts, int) and _diamond_buy_ts > 1000000000:
            last_diamond_purchase = format_timestamp(_diamond_buy_ts)
        else:
            last_diamond_purchase = "N/A"

        starlight_count = 0
        if role_info and isinstance(role_info, dict):
            starlight_count = role_info.get(60, 0)

        skin_history = []
        if role_info and isinstance(role_info, dict):
            _tag92 = role_info.get(92, [])
            if isinstance(_tag92, list):
                for _entry in _tag92[:5]:
                    if isinstance(_entry, dict):
                        _sid  = _entry.get(0, 0)
                        _tier = _entry.get(2, 0)
                        _ts   = _entry.get(4, 0)
                        _tier_name = {1:"Common",2:"Exceptional",3:"Deluxe",
                                      4:"Exquisite",5:"Grand",6:"Supreme"}.get(_tier, f"T{_tier}")
                        _date = format_timestamp(_ts) if _ts else "?"
                        skin_history.append(f"SkinID:{_sid}({_tier_name})|{_date}")
        skin_history_str = ", ".join(skin_history) if skin_history else "N/A"

        _EMBLEM_MAP = {1:"Fighter",2:"Assassin",3:"Mage",4:"Marksman",
                       5:"Support",6:"Tank",7:"Common"}
        emblem_levels = "N/A"
        if role_info and isinstance(role_info, dict):
            _tag101 = role_info.get(101, {})
            if isinstance(_tag101, dict) and _tag101:
                _parts = []
                for _eid in sorted(_tag101.keys()):
                    _ename = _EMBLEM_MAP.get(_eid, f"E{_eid}")
                    _parts.append(f"{_ename}:Lv{_tag101[_eid]}")
                emblem_levels = ", ".join(_parts) if _parts else "N/A"

        skin_counts = {
            "Supreme Skins":     0, "Grand Skins":       0,
            "Exquisite Skins":   0, "Deluxe Skins":      0,
            "Exceptional Skins": 0, "Common Skins":      0,
        }
        _tag118 = None
        if role_info and isinstance(role_info, dict):
            _tag118 = role_info.get(118)
        if not _tag118:
            _tag118 = player_data.get(118)
        if _tag118:
            _parsed_skins = parse_skin_counts(_tag118)
            if _parsed_skins:
                skin_counts.update(_parsed_skins)

        # ── ban sniff (stub-safe; ban_info authoritative) ────────────
        ban_detected, detected_info = inspect_ban(result)
        if not ban_detected and role_info:
            b2, i2 = inspect_ban(role_info)
            if b2:
                ban_detected, detected_info = True, i2
        if ban_info and isinstance(ban_info, dict) and ban_info:
            # only accept connection-level ban if it carries real signal
            day = ban_info.get('endtime_day')
            try:
                d = int(day) if day is not None else None
            except (TypeError, ValueError):
                d = None
            has_signal = (
                (d is not None and d > 0) or
                (d is not None and d > 1_000_000_000) or
                str(ban_info.get('ban_status_raw', '')).strip().lower()
                    in ('1', 'true', 'yes', 'banned', 'ban')
            )
            if has_signal:
                ban_detected = True
                merged = dict(detected_info)
                merged.update(ban_info)
                detected_info = merged

        if ban_detected and not detected_info.get('reason_name'):
            code = detected_info.get('ban_code') or '21'
            detected_info['ban_code']   = code
            detected_info['reason_name'] = BAN_REASONS.get(
                code, 'Using Plug-in Apps to Compromise Competitive Fairness')

        bindings_str = extract_bindings(player_data)

        return {
            'nickname': nickname, 'player_id': player_id, 'server': server, 'level': level,
            'skin_count': skin, 'hero_count': hero_count, 'matches': matches,
            'rating_score': rating_score, 'location': location,
            'last_login': last_login_formatted, 'last_login_country': last_login_country,
            'create_account_country': create_account_country,
            'high_rank': high_rank, 'current_rank': current_rank,
            'achievement_points': achievement_points,
            'collector_point': collector_point, 'collector_rank': collector_rank,
            'collector_tier': collector_tier, 'hero_history': hero_history,
            'squad': squad, 'squad_id': squad_id_display, 'skin_breakdown': skin_counts,
            'affinity': affinity_label, 'likes': likes,
            'credits_score': credits_score if credits_score and credits_score != "N/A" else None,
            'followers': followers, 'popularity': popularity,
            'bio': bio if bio else None,
            'latest_skin_date': latest_skin_date,
            'latest_skin_tier': latest_skin_tier,
            'starlight_user': starlight_user, 'starlight_expiry': starlight_expiry,
            'starlight_months': starlight_months if starlight_months else None,
            'tickets': tickets if tickets else None,
            'total_wins': total_wins if total_wins else None,
            'restriction_flags': restriction_flags,
            'last_heroes_purchase': last_heroes_purchase,
            'mcl_champion_wins': mcl_wins,
            'v2l_status': v2l_status, 'creation_date': creation_date,
            'account_age': account_age, 'win_count': win_count,
            'total_battles': total_battles, 'win_rate': win_rate,
            'battle_points': bp if bp else None,
            'diamonds': diamonds if diamonds else None,
            'last_diamond_purchase': last_diamond_purchase if last_diamond_purchase != "N/A" else None,
            'squad_motto': squad_motto if squad_motto and squad_motto != "N/A" else None,
            'starlight_count': starlight_count if starlight_count else None,
            'skin_history': skin_history_str if skin_history_str and skin_history_str != "N/A" else None,
            'emblem_levels': emblem_levels if emblem_levels and emblem_levels != "N/A" else None,
            'latest_skin_id': latest_skin_id_str if latest_skin_id_str != "N/A" else None,
            'bindings': bindings_str,
            'ban_status': 'BANNED' if ban_detected else 'CLEAN',
            'ban_code': (detected_info.get('ban_code') if ban_detected else None),
            'ban_reason': (detected_info.get('reason_name') if ban_detected else None),
            'ban_duration': (format_ban_duration(detected_info) if ban_detected else None),
        }
    except Exception:
        return None


def lookup_player_data(player_id_or_nickname, server_id=None, guid=None, session=None, combo_v2l=None):
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
                return {"error": "Server ID is required when searching by nickname", "status": "error"}
            try:
                server_filter = int(server_id)
            except ValueError:
                return {"error": "Server ID must be a number", "status": "error"}

        device_ids = load_device_ids()
        device_models = load_device_models()
        if not device_ids:
            return {"error": "No device IDs available - check device_ids.txt", "status": "error"}

        retry_count = 0
        max_retries = 10
        result = None
        _creation_ts = 0
        current_device_ids = device_ids.copy()
        last_error = None
        _v2l_data = None
        role_info_data = None

        while retry_count < max_retries and result is None and current_device_ids:
            current_device_id = random.choice(current_device_ids)
            current_device_model = random.choice(device_models) if device_models else None
            try:
                with GameConnection(device_id=current_device_id, device_model=current_device_model) as conn:

                    if conn.ban_seen:
                        _pd = conn._banned_player_data(None, role_info_data, _v2l_data)
                        return {"status": "success", "player_data": _pd}

                    if not conn.connect_to_game_server():
                        last_error = "Failed to connect to game server"
                        if current_device_id in current_device_ids:
                            current_device_ids.remove(current_device_id)
                        retry_count += 1
                        continue

                    if conn.ban_seen:
                        _pd = conn._banned_player_data(None, role_info_data, _v2l_data)
                        return {"status": "success", "player_data": _pd}

                    result = conn.lookup_player(search_value, search_type, server_filter)
                    _creation_ts = conn.creation_ts

                    if conn.ban_seen:
                        _pd = conn._banned_player_data(result, role_info_data, _v2l_data)
                        return {"status": "success", "player_data": _pd}

                    if result is None:
                        last_error = "Lookup returned None"
                        retry_count += 1
                        role_info_data = None
                    else:
                        _res_role_id = result[0][0].get(0, search_value) if (result and result[0]) else search_value
                        _res_zone_id = result[0][0].get(1, 0) if (result and result[0]) else 0
                        role_info_data = None
                        try:
                            skin_role_info = conn.get_skin_role_info(_res_role_id, _res_zone_id)
                            if skin_role_info and isinstance(skin_role_info, dict):
                                role_info_data = dict(skin_role_info)
                        except Exception as e:
                            last_error = f"Skin role info failed: {str(e)}"
                        try:
                            full_role_info = conn.get_role_info(_res_role_id, _res_zone_id)
                            if full_role_info and isinstance(full_role_info, dict):
                                if role_info_data is None:
                                    role_info_data = {}
                                for _k, _v in full_role_info.items():
                                    if _k not in role_info_data or not role_info_data[_k]:
                                        role_info_data[_k] = _v
                        except Exception as e:
                            dbg(f"Full role info fetch failed: {e}", color=Fore.RED)

                        if conn.ban_seen:
                            _pd = conn._banned_player_data(result, role_info_data, _v2l_data)
                            return {"status": "success", "player_data": _pd}

                        _v2l_data = None
                        try:
                            _v2l_data = conn.get_v2l_status(_res_role_id, _res_zone_id)
                        except Exception as e:
                            dbg(f"V2L status fetch failed: {e}", color=Fore.RED)

                        if conn.ban_seen:
                            _pd = conn._banned_player_data(result, role_info_data, _v2l_data)
                            return {"status": "success", "player_data": _pd}

            except ConnectionError as e:
                error_msg = str(e)
                last_error = f"Connection error: {error_msg}"
                if "LOGIN_FAILED" in error_msg:
                    remove_failed_device_id(current_device_id)
                if current_device_id in current_device_ids:
                    current_device_ids.remove(current_device_id)
                retry_count += 1
                if not current_device_ids:
                    current_device_ids = load_device_ids()
                    if not current_device_ids:
                        break
            except socket.timeout as e:
                last_error = f"Socket timeout: {str(e)}"
                if current_device_id in current_device_ids:
                    current_device_ids.remove(current_device_id)
                retry_count += 1
            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__}: {str(e)}"
                if current_device_id in current_device_ids:
                    current_device_ids.remove(current_device_id)
                retry_count += 1

        if result:
            _ban_seen, _ban_info = inspect_ban(result)
            if not _ban_seen and role_info_data:
                _b2, _i2 = inspect_ban(role_info_data)
                if _b2:
                    _ban_seen, _ban_info = True, _i2
            player_data = extract_player_data(
                result,
                role_info=role_info_data,
                creation_ts=_creation_ts,
                v2l_data=_v2l_data,
                ban_info=(_ban_info if _ban_seen else None),
            )
            if player_data:
                if player_data.get('v2l_status', 'N/A') == 'N/A' and combo_v2l:
                    player_data['v2l_status'] = combo_v2l
                return {"status": "success", "player_data": player_data}
            else:
                return {"error": "Error extracting player data from result", "status": "error"}
        else:
            if last_error:
                return {"error": last_error, "status": "error"}
            return {"error": "Player not found after all retries", "status": "error"}
    except Exception as e:
        return {"error": f"Critical error in lookup: {type(e).__name__}: {str(e)}", "status": "error"}


def build_save_block(account_info, player_data, hit_num):
    email      = account_info.get("email", "?")
    password   = account_info.get("password", "?")
    v2l        = player_data.get("v2l_status", account_info.get("V2L", account_info.get("V2L Status", "N/A")))
    guid       = account_info.get("GUID", "N/A")
    session    = account_info.get("Session", "N/A")
    level      = account_info.get("Level", player_data.get("level", "N/A"))
    role_id    = account_info.get("Role ID", account_info.get("role_id", "N/A"))
    zone_id    = account_info.get("Zone ID", account_info.get("zone_id", "N/A"))
    uid        = account_info.get("UID", "N/A")
    region     = account_info.get("Region", "N/A")
    c_rank     = player_data.get("current_rank", account_info.get("Current Rank", "N/A"))
    h_rank     = player_data.get("high_rank", account_info.get("Highest Rank", "N/A"))

    bindings   = player_data.get("bindings") or account_info.get("Bindings", "N/A")
    ban_status = player_data.get("ban_status") or account_info.get("Ban Status", "N/A")
    ban_reason = player_data.get("ban_reason")
    ban_duration = player_data.get("ban_duration")
    ban_code   = player_data.get("ban_code")

    name             = player_data.get("nickname", "N/A")
    skin_count       = player_data.get("skin_count", 0)
    hero_count       = player_data.get("hero_count", 0)
    collector_point  = player_data.get("collector_point", 0)
    collector_tier   = player_data.get("collector_tier", "N/A")
    achievement_pts  = player_data.get("achievement_points", 0)
    squad            = player_data.get("squad", "—")
    last_login       = player_data.get("last_login", "N/A")
    location         = player_data.get("location", "NOT FOUND")
    hero_history_raw = player_data.get("hero_history", [])
    hero_history_str = ", ".join(hero_history_raw) if hero_history_raw else "N/A"
    create_account_country = player_data.get("create_account_country", "N/A")
    rating_score     = player_data.get("rating_score", 0)
    affinity        = player_data.get("affinity", 0)
    likes           = player_data.get("likes", 0)
    credits_score   = player_data.get("credits_score", 0)
    followers       = player_data.get("followers", 0)
    popularity      = player_data.get("popularity", 0)
    latest_skin_date = player_data.get("latest_skin_date", "N/A")
    latest_skin_id   = player_data.get("latest_skin_id", "N/A")
    latest_skin_tier = player_data.get("latest_skin_tier") or "N/A"
    starlight_user  = player_data.get("starlight_user", "N/A")
    restriction_flags = player_data.get("restriction_flags", "None")
    last_heroes_purchase = player_data.get("last_heroes_purchase", "N/A")
    mcl_champion_wins = player_data.get("mcl_champion_wins", 0)
    creation_date   = player_data.get("creation_date", "N/A")
    diamonds        = player_data.get("diamonds", 0) or 0
    battle_points   = player_data.get("battle_points", 0) or 0
    tickets_bd      = player_data.get("tickets", 0) or 0
    last_diamond_purchase = player_data.get("last_diamond_purchase", "N/A") or "N/A"
    SEP = "=" * 70
    W   = 25
    lines = [
        SEP,
        f"  VALID HIT #{hit_num}",
        SEP,
        f"  {'LOGIN:':<{W}} {email}:{password}",
        f"  {'V2L Status:':<{W}} {v2l}",
        f"  {'NAME:':<{W}} {name}",
        f"  {'LEVEL:':<{W}} {level}",
        f"  {'Country:':<{W}} {create_account_country}",
        f"  {'Creation Date:':<{W}} {creation_date}",
        f"  {'Skin Count:':<{W}} {skin_count}",
        f"  {'Hero Count:':<{W}} {hero_count}",
        f"  {'Collector Point:':<{W}} {collector_point}",
        f"  {'Collector Tier:':<{W}} {collector_tier}",
        f"  {'Supreme Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Supreme Skins', 0)}",
        f"  {'Grand Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Grand Skins', 0)}",
        f"  {'Exquisite Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Exquisite Skins', 0)}",
        f"  {'Deluxe Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Deluxe Skins', 0)}",
        f"  {'Exceptional Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Exceptional Skins', 0)}",
        f"  {'Common Skins':<{W}} : {player_data.get('skin_breakdown', {}).get('Common Skins', 0)}",
        f"  {'Achievement Points:':<{W}} {achievement_pts}",
        f"  {'Squad:':<{W}} {squad}",
        f"  {'CURRENT RANK:':<{W}} {c_rank}",
        f"  {'HIGHEST RANK:':<{W}} {h_rank}",
        f"  {'BINDINGS:':<{W}} {bindings}",
        f"  {'BAN STATUS:':<{W}} {ban_status}",
        *([ f"  {'Ban Code:':<{W}} {ban_code}"] if ban_code else []),
        *([ f"  {'Ban Reason:':<{W}} {ban_reason}"] if ban_reason else []),
        *([ f"  {'Ban Duration:':<{W}} {ban_duration}"] if ban_duration else []),
        f"  {'MLBB INFO: Region:':<{W}} {region}",
        f"  {'UID:':<{W}} {uid}",
        f"  {'Role ID:':<{W}} {role_id}",
        f"  {'Zone ID:':<{W}} {zone_id}",
        f"  {'GUID:':<{W}} {guid}",
        f"  {'Session:':<{W}} {session}",
        f"  {'Last Login:':<{W}} {last_login}",
        f"  {'Location:':<{W}} {location}",
        "",
        f"  {'Rating Score:':<{W}} {rating_score}",
        f"  {'Affinity:':<{W}} {affinity}",
        f"  {'Likes:':<{W}} {likes}",
        *([ f"  {'Credits Score:':<{W}} {credits_score}"] if credits_score and credits_score != "N/A" else []),
        f"  {'Followers:':<{W}} {followers}",
        f"  {'Popularity:':<{W}} {popularity}",
        *([ f"  {'Bio:':<{W}} {player_data.get('bio', 'N/A')}"] if player_data.get('bio') else []),
        f"  {'Latest Skin Purchase Date:':<{W}} {latest_skin_date}",
        f"  {'Latest Skin ID:':<{W}} {latest_skin_id}",
        f"  {'Latest Skin Tier:':<{W}} {latest_skin_tier}",
        f"  {'Starlight User:':<{W}} {starlight_user}",
        f"  {'Restriction Flags:':<{W}} {restriction_flags}",
        f"  {'Last Heroes Purchase:':<{W}} {last_heroes_purchase}",
        f"  {'MCL Champion Wins:':<{W}} {mcl_champion_wins}",
        "",
        f"  {'Total Battles:':<{W}} {player_data.get('total_battles', 0)}",
        f"  {'Win Rate:':<{W}} {player_data.get('win_rate', 'N/A')}",
        f"  {'Diamonds:':<{W}} {diamonds}",
        f"  {'Battle Points (BP):':<{W}} {battle_points}",
        f"  {'Tickets:':<{W}} {tickets_bd}",
        *([ f"  {'Last Diamond Purchase:':<{W}} {last_diamond_purchase}"] if last_diamond_purchase != 'N/A' else []),
        "",
        f"  {'History:':<{W}} {hero_history_str}",
        SEP,
        "",
    ]
    return "\n".join(lines)


def print_full_info(player_data):
    """Print the FULL captured information to terminal (no save)."""
    if not player_data:
        print(f"{Fore.RED}No player data.{Style.RESET_ALL}")
        return

    SEP = "=" * 70

    print(f"\n{Fore.CYAN}{SEP}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  PLAYER INFORMATION{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{SEP}{Style.RESET_ALL}")

    dummy_acc = {
        "email": "N/A", "password": "N/A",
        "GUID": "N/A", "Session": "N/A",
        "Level": player_data.get("level", "N/A"),
        "Role ID": player_data.get("player_id", "N/A"),
        "Zone ID": player_data.get("server", "N/A"),
        "UID": f"{player_data.get('player_id', 'N/A')} ({player_data.get('server', 'N/A')})",
        "Region": player_data.get("create_account_country", "N/A"),
        "Bindings": "N/A",
        "Ban Status": "N/A",
    }
    block = build_save_block(dummy_acc, player_data, 1)
    block_lines = block.split("\n")
    for line in block_lines:
        if line.startswith("=" * 70):
            print(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
        elif ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0]
                val = parts[1]
                print(f"  {Fore.GREEN}{key.strip():<25}{Style.RESET_ALL}: {Fore.WHITE}{val.strip()}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.WHITE}{line.strip()}{Style.RESET_ALL}")
        elif line.strip() == "":
            print()
        else:
            print(f"  {Fore.WHITE}{line.strip()}{Style.RESET_ALL}")

    print(f"{Fore.CYAN}{SEP}{Style.RESET_ALL}\n")


def run_id_server_lookup():
    """Prompt: Put your Server Id example 1234474 2345 or 2938383 Id only"""
    print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  ID + SERVER LOOKUP{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Put your Server Id example 1234474 2345 or 2938383 Id only{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  Format: <ID> <SERVER>   or   <ID>   (or nickname + server){Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  Examples:{Style.RESET_ALL}")
    print(f"    {Fore.WHITE}1234474 2345{Style.RESET_ALL}   → ID + server")
    print(f"    {Fore.WHITE}2938383{Style.RESET_ALL}        → ID only")
    print(f"    {Fore.WHITE}SomeNickname 2345{Style.RESET_ALL} → nickname + server")
    print(f"{Fore.YELLOW}  Type 'exit' or 'q' to quit.{Style.RESET_ALL}")

    raw = input(f"\n{Fore.CYAN}Enter ID (or nickname) [server]: {Style.RESET_ALL}").strip()
    if not raw:
        print(f"{Fore.RED}No input. Cancelled.{Style.RESET_ALL}")
        return False

    if raw.lower() in ("exit", "q", "quit"):
        return None

    parts = raw.split()
    player_id_input = parts[0]
    server_input    = parts[1] if len(parts) > 1 else None

    try:
        int(player_id_input)
        is_id_lookup = True
    except ValueError:
        is_id_lookup = False

    if not is_id_lookup and not server_input:
        print(f"{Fore.RED}Nickname lookup requires server ID. Example: SomeName 2345{Style.RESET_ALL}")
        return False

    print(f"\n{Fore.CYAN}Looking up: {player_id_input}{f' (server {server_input})' if server_input else ''} ...{Style.RESET_ALL}\n")

    result = lookup_player_data(player_id_input, server_input)

    if result.get("status") == "success":
        player_data = result.get("player_data", {})
        print(f"{Fore.GREEN}✓ Lookup successful!{Style.RESET_ALL}")
        print_full_info(player_data)
    else:
        err = result.get("error", "Unknown error")
        print(f"{Fore.RED}✗ Lookup failed: {err}{Style.RESET_ALL}\n")

    return True


def main():
    print(f"{Fore.GREEN}")
    for line in [
        r"███    ███ ██           ██████ ██   ██ ███████  ██████ ██   ██ ███████ ██████  ",
        r"████  ████ ██          ██      ██   ██ ██      ██      ██  ██  ██      ██   ██ ",
        r"██ ████ ██ ██          ██      ███████ █████   ██      █████   █████   ██████  ",
        r"██  ██  ██ ██          ██      ██   ██ ██      ██      ██  ██  ██      ██   ██ ",
        r"██      ██ ███████      ██████ ██   ██ ███████  ██████ ██   ██ ███████ ██   ██ ",
    ]:
        print(line)
    print(f"{Style.RESET_ALL}")
    print(f"{Fore.GREEN} MLBB Full Info Checker{Style.RESET_ALL}")

    while True:
        try:
            cont = run_id_server_lookup()
            if cont is None:
                print(f"{Fore.GREEN}Bye!{Style.RESET_ALL}")
                sys.exit(0)
        except KeyboardInterrupt:
            print(f"\n{Fore.GREEN}Bye!{Style.RESET_ALL}")
            sys.exit(0)


if __name__ == "__main__":
    main()
