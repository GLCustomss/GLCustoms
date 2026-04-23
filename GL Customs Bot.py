import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
import random
import io
import math
from datetime import datetime, timedelta, timezone

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = os.getenv("TOKEN")

MODLOG_CHANNEL_ID = 1480303268981641256
ALT_ACCOUNT_CHANNEL_ID = 1471186783461969940
REWARD_ANNOUNCEMENT_CHANNEL_ID = 1480303268981641256
LOGO_URL = "https://cdn.discordapp.com/icons/1257758348984451093/3d3faa841eff8e93f5fb3787a5a3ef5d.png?size=4096"

REGULAR_MEMBER_ROLE_ID = 1381357053288644638
SECURITY_TEAM_ROLE_ID = 1480515604476854302
INFRASTRUCTURE_ROLE_ID = 1480875161895960748

ROLE_COMMAND_BYPASS_USER_IDS = {
    793613955003318273,
}

UNBAN_GBAN_BYPASS_USER_IDS = {
    793613955003318273,
}

PROTECTED_ROLE_IDS = {
    # add protected role IDs here if needed
}

BLACKLISTED_ROLE_ID = 1454606643617861733

BLOCKED_ROLE_IDS = {
    1454606643617861733,  # blacklisted
    1458868954092011694,  # muted
    1475164591171440823,  # bots
    1257759991612444825,  # management
    1443695766832021556,  # role perms
    1456971346373251237,  # vault access
    1369083934687756359,  # ban perms
    1386829989445632181,  # senior management
    1398090447221428414,  # head management
    1257759839044763658,  # co-owner
}

MUTED_ROLE_ID = 1458868954092011694
ALT_ACCOUNT_DAYS = 3

CONFIRM_TIMEOUT_SECONDS = 5
CONFIRM_CLEANUP_DELAY_SECONDS = 10
GAME_XP_PER_PLAY = 10
CASINO_CAR_PACK_ROLE_ID = 1487023725063835668
MAX_GIVE_AMOUNT = 100000
INFINITE_CASH_VALUE = 10**100
INFINITE_GAME_DISPLAY_BET = 1000000000000
OWNER_ID = 793613955003318273
CASINO_CAR_PACK_THRESHOLD = 100000000000000
WEEKLY_REWARD_AMOUNTS = {1: 1000000, 2: 500000, 3: 250000}
BEG_STREAK_BONUS = 3000
WORK_STREAK_BONUS = 10000
STREAK_RESET_HOURS = 48
MINES_JACKPOT_CHANCE = 0.035
MINES_JACKPOT_MIN = 10000
MINES_JACKPOT_MAX = 150000
PLINKO_MULTIPLIERS = [7.0, 3.25, 2.0, 1.25, 1.0, 0.82, 1.0, 1.25, 2.0, 3.25, 7.0]
BETTING_COOLDOWN_SECONDS = 3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "gl_customs_data.json")

GAME_COMMAND_NAMES = {
    "coinflip", "roll", "eightball", "choose", "rps", "guess", "number",
    "slots", "rate", "ship", "trivia", "fortune", "compliment", "wyr",
    "truth", "dare", "emoji", "colourpick", "animalpick", "foodpick",
    "carpick", "countrypick", "superpower", "mysterybox", "race", "battle",
    "reverse", "say", "fact", "memeidea", "scramble", "achievement", "namegen", "mines", "mine", "bj", "blackjack", "balance", "bal", "beg", "work", "give", "plinko", "rocket", "rewards", "removecash",
    "roulette", "crash", "dice", "baccarat", "chess"
}

# =========================================================
# V3 GAME RESPONSE POOLS (expanded variations)
# =========================================================
EIGHTBALL_RESPONSES = [
    "Yes.", "No.", "Definitely.", "Absolutely not.", "The odds look good.",
    "The signs point to yes.", "The signs point to no.", "Try again later.",
    "Ask again in a bit.", "It’s unclear right now.", "Without a doubt.",
    "Very likely.", "Highly unlikely.", "Better not tell you now.",
    "I wouldn’t count on it.", "Chances are strong.", "Focus and ask again.",
    "All indicators say yes.", "All indicators say no.", "Possibly.",
]

COINFLIP_RESPONSES = [
    "The coin spins through the air… **{result}!**",
    "You flip the coin… it lands on **{result}!**",
    "The coin rolls across the floor… **{result}!**",
    "A shiny flip… **{result}!**",
    "After a dramatic spin… **{result}!**"
]

ROLL_RESPONSES = [
    "The dice tumble across the table… **{value}!**",
    "You roll the dice… it lands on **{value}!**",
    "The cube spins wildly… **{value}!**",
    "A lucky throw gives you **{value}!**"
]

SLOT_EMOJIS = ["🍒","🍋","🍉","⭐","💎","7️⃣"]

ACTIVE_GAME_USERS = set()


# =========================================================
# BOT SETUP
# =========================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# =========================================================
# SMART TYPING SYSTEM
# =========================================================
NO_TYPING_DELAY_COMMANDS = {"purge", "clean", "auditlog"}


@bot.before_invoke
async def before_any_command(ctx):
    if ctx.command and ctx.command.name in NO_TYPING_DELAY_COMMANDS:
        ctx._typing_cm = None
        return

    try:
        ctx._typing_cm = ctx.channel.typing()
        await ctx._typing_cm.__aenter__()
        await asyncio.sleep(random.uniform(0.9, 1.6))
    except Exception:
        ctx._typing_cm = None


@bot.after_invoke
async def after_any_command(ctx):
    if getattr(ctx, "_typing_cm", None) is not None:
        try:
            await ctx._typing_cm.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            ctx._typing_cm = None

    try:
        if (
            ctx.command
            and ctx.command.name in GAME_COMMAND_NAMES
            and has_regular_member_permission(ctx.author)
        ):
            award_game_xp(ctx.author.id, ctx.command.name)
    except Exception:
        pass

# =========================================================
# DATA
# =========================================================
def default_data():
    return {
        "case_counters": {},
        "cases": {},
        "rolestrip_saved": {},
        "blacklist_saved": {},
        "warnings": {},
        "notes": {},
        "global_bans": {},
        "temp_roles": {},
        "lock_saved": {},
        "lockdown_saved": {},
        "leaderboard": {},
        "balances": {},
        "cooldowns": {},
        "streaks": {},
        "weekly_rewards": {"last_payout": None},
        "casino_profit": {"totals": {}, "history": []},
        "casino_user_stats": {}
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data()

    base = default_data()
    for key, value in base.items():
        if key not in data:
            data[key] = value
    return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def next_case_id(case_key):
    data = load_data()
    counters = data.setdefault("case_counters", {})
    counters[case_key] = counters.get(case_key, 0) + 1
    save_data(data)
    return counters[case_key]


def now_dt():
    return datetime.now(timezone.utc)


def now_str():
    return now_dt().strftime("%d-%m-%Y %H:%M")


def now_iso():
    return now_dt().isoformat()

# =========================================================
# SAVE HELPERS
# =========================================================
def record_case(case_id, action, user_id, staff_id, reason):
    data = load_data()
    data["cases"][str(case_id)] = {
        "action": str(action),
        "user_id": str(user_id),
        "staff_id": str(staff_id),
        "reason": str(reason) if reason else "None",
        "date": now_str(),
        "timeline": [
            {
                "type": "created",
                "action": str(action),
                "staff_id": str(staff_id),
                "reason": str(reason) if reason else "None",
                "date": now_str()
            }
        ]
    }
    save_data(data)


def append_case_timeline(case_id, event_type, staff_id, text):
    data = load_data()
    case = data["cases"].get(str(case_id))
    if not case:
        return

    case.setdefault("timeline", []).append({
        "type": str(event_type),
        "staff_id": str(staff_id),
        "text": str(text),
        "date": now_str()
    })
    save_data(data)


def save_rolestrip_roles(user_id, role_ids):
    data = load_data()
    data["rolestrip_saved"][str(user_id)] = role_ids
    save_data(data)


def get_rolestrip_roles(user_id):
    data = load_data()
    return data["rolestrip_saved"].get(str(user_id))


def delete_rolestrip_roles(user_id):
    data = load_data()
    if str(user_id) in data["rolestrip_saved"]:
        del data["rolestrip_saved"][str(user_id)]
        save_data(data)


def save_blacklist_roles(user_id, role_ids):
    data = load_data()
    data["blacklist_saved"][str(user_id)] = role_ids
    save_data(data)


def get_blacklist_roles(user_id):
    data = load_data()
    return data["blacklist_saved"].get(str(user_id))


def delete_blacklist_roles(user_id):
    data = load_data()
    if str(user_id) in data["blacklist_saved"]:
        del data["blacklist_saved"][str(user_id)]
        save_data(data)


def add_warning(user_id, staff_id, reason):
    data = load_data()
    warnings = data["warnings"].setdefault(str(user_id), [])
    warnings.append({
        "staff_id": str(staff_id),
        "reason": str(reason),
        "date": now_str()
    })
    save_data(data)
    return len(warnings)


def get_warnings(user_id):
    data = load_data()
    return data["warnings"].get(str(user_id), [])


def clear_warnings(user_id):
    data = load_data()
    if str(user_id) in data["warnings"]:
        del data["warnings"][str(user_id)]
        save_data(data)


def add_note(user_id, staff_id, note):
    data = load_data()
    notes = data["notes"].setdefault(str(user_id), [])
    notes.append({
        "staff_id": str(staff_id),
        "note": str(note),
        "date": now_str()
    })
    save_data(data)
    return len(notes)


def get_notes(user_id):
    data = load_data()
    return data["notes"].get(str(user_id), [])


def clear_notes(user_id):
    data = load_data()
    if str(user_id) in data["notes"]:
        del data["notes"][str(user_id)]
        save_data(data)


def add_global_ban(user_id, staff_id, reason):
    data = load_data()
    data["global_bans"][str(user_id)] = {
        "staff_id": str(staff_id),
        "reason": str(reason),
        "date": now_str()
    }
    save_data(data)


def get_global_ban(user_id):
    data = load_data()
    return data["global_bans"].get(str(user_id))


def remove_global_ban(user_id):
    data = load_data()
    if str(user_id) in data["global_bans"]:
        del data["global_bans"][str(user_id)]
        save_data(data)
        return True
    return False


def is_globally_banned(user_id):
    data = load_data()
    return str(user_id) in data["global_bans"]


def add_temp_role(user_id, guild_id, role_id, staff_id, expires_at_iso):
    data = load_data()
    temp_roles = data.setdefault("temp_roles", {})
    user_roles = temp_roles.setdefault(str(user_id), [])
    user_roles.append({
        "guild_id": str(guild_id),
        "role_id": str(role_id),
        "staff_id": str(staff_id),
        "expires_at": expires_at_iso
    })
    save_data(data)


def get_temp_roles():
    data = load_data()
    return data.get("temp_roles", {})


def save_temp_roles(temp_roles):
    data = load_data()
    data["temp_roles"] = temp_roles
    save_data(data)


def get_user_game_stats(user_id):
    data = load_data()
    leaderboard = data.setdefault("leaderboard", {})
    return leaderboard.setdefault(str(user_id), {
        "xp": 0,
        "games_played": 0,
        "command_counts": {}
    })


def save_user_game_stats(user_id, stats):
    data = load_data()
    leaderboard = data.setdefault("leaderboard", {})
    leaderboard[str(user_id)] = stats
    save_data(data)


def get_user_balance(user_id):
    data = load_data()
    balances = data.setdefault("balances", {})
    if str(user_id) not in balances:
        balances[str(user_id)] = 0
        save_data(data)
    return int(balances[str(user_id)])


def set_user_balance(user_id, amount):
    data = load_data()
    balances = data.setdefault("balances", {})
    balances[str(user_id)] = max(0, int(amount))
    save_data(data)


def add_user_balance(user_id, amount):
    current = get_user_balance(user_id)
    set_user_balance(user_id, current + int(amount))
    return get_user_balance(user_id)


def remove_user_balance(user_id, amount):
    current = get_user_balance(user_id)
    if is_infinite_cash(current):
        return True, current
    if current < int(amount):
        return False, current
    set_user_balance(user_id, current - int(amount))
    return True, get_user_balance(user_id)


def parse_cash_amount(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    text = str(raw_value).strip().lower().replace(",", "")
    if not text:
        return None

    multipliers = {
        "k": 10**3,
        "m": 10**6,
        "b": 10**9,
        "t": 10**12,
        "qd": 10**15,
        "qi": 10**18,
        "q": 10**15,
        "qq": 10**18,
    }

    for suffix in ["qq", "qi", "q", "qd", "t", "b", "m", "k"]:
        if text.endswith(suffix):
            number_part = text[:-len(suffix)].strip()
            if not number_part:
                return None
            return int(float(number_part) * multipliers[suffix])

    return int(float(text))

def format_cash(amount):
    try:
        if isinstance(amount, str):
            amount = amount.replace(",", "").strip()
        if int(amount) >= INFINITE_CASH_VALUE:
            return "∞"
        negative = float(amount) < 0
        amount = abs(float(amount))
    except Exception:
        negative = False
        amount = 0.0

    suffixes = [
        (10**33, "dc"),
        (10**30, "no"),
        (10**27, "oc"),
        (10**24, "sp"),
        (10**21, "sx"),
        (10**18, "qq"),
        (10**15, "q"),
        (10**12, "t"),
        (10**9, "b"),
        (10**6, "m"),
        (10**3, "k"),
    ]

    if amount < 1000:
        value = str(int(amount)) if amount.is_integer() else f"{amount:.2f}".rstrip("0").rstrip(".")
    else:
        value = str(int(amount))
        for threshold, suffix in suffixes:
            if amount >= threshold:
                scaled = amount / threshold
                if scaled >= 100:
                    value = f"{scaled:.0f}{suffix}"
                elif scaled >= 10:
                    value = f"{scaled:.1f}".rstrip("0").rstrip(".") + suffix
                else:
                    value = f"{scaled:.2f}".rstrip("0").rstrip(".") + suffix
                break

    return f"-{value}" if negative else value


def is_infinite_cash(amount):
    try:
        return int(amount) >= INFINITE_CASH_VALUE
    except Exception:
        return False


def result_display_amount(amount, balance_reference=None):
    try:
        value = int(amount)
    except Exception:
        return amount

    if balance_reference is not None and is_infinite_cash(balance_reference) and is_infinite_cash(value):
        return INFINITE_CASH_VALUE
    return value


def format_result_cash(amount, balance_reference=None):
    return format_cash(result_display_amount(amount, balance_reference))


def should_display_casino_infinite(display_bet_amount):
    try:
        return is_infinite_cash(display_bet_amount)
    except Exception:
        return False


def format_casino_bet_display(amount=None, display_bet_amount=None):
    value = display_bet_amount if display_bet_amount is not None else amount
    if should_display_casino_infinite(value):
        return "∞"

    try:
        return format_cash(int(value))
    except Exception:
        return format_cash(value)


def format_casino_result_display(amount, balance_reference=None, display_bet_amount=None):
    if should_display_casino_infinite(display_bet_amount):
        return "∞"
    return format_result_cash(amount, balance_reference)


def format_mines_bet_display(amount):
    return format_casino_bet_display(display_bet_amount=amount)


def should_display_mines_infinite(display_bet_amount):
    return should_display_casino_infinite(display_bet_amount)


def format_mines_cashout_result(amount, balance_reference=None, display_bet_amount=None):
    return format_casino_result_display(amount, balance_reference, display_bet_amount)


def round_mines_display_amount(amount):
    try:
        amount = int(amount)
    except Exception:
        return 0

    if amount <= 0:
        return 0

    if amount >= 10**18:
        step = 10**15
    elif amount >= 10**15:
        step = 10**12
    elif amount >= 10**12:
        step = 10**9
    elif amount >= 10**9:
        step = 10**6
    elif amount >= 10**6:
        step = 10**6
    elif amount >= 10**3:
        step = 10**3
    else:
        return amount

    return max(step, int(round(amount / step) * step))


def get_profit_data():
    data = load_data()
    casino_profit = data.setdefault("casino_profit", {"totals": {}, "history": []})
    casino_profit.setdefault("totals", {})
    casino_profit.setdefault("history", [])
    return casino_profit


def get_casino_user_stats(user_id):
    data = load_data()
    stats_root = data.setdefault("casino_user_stats", {})
    return stats_root.setdefault(str(user_id), {
        "wagered": 0,
        "paid_out": 0,
        "net": 0,
        "plays": 0,
        "biggest_win": 0,
        "game_counts": {}
    })


def save_casino_user_stats(user_id, stats):
    data = load_data()
    stats_root = data.setdefault("casino_user_stats", {})
    stats_root[str(user_id)] = stats
    save_data(data)


def record_house_profit(game_name, wager, payout, user_id=None):
    try:
        wager = int(wager)
        payout = int(payout)
    except Exception:
        return

    net = wager - payout
    data = load_data()
    casino_profit = data.setdefault("casino_profit", {"totals": {}, "history": []})
    totals = casino_profit.setdefault("totals", {})
    history = casino_profit.setdefault("history", [])

    game = totals.setdefault(str(game_name), {
        "wagered": 0,
        "paid_out": 0,
        "house_profit": 0,
        "plays": 0
    })
    game["wagered"] += wager
    game["paid_out"] += payout
    game["house_profit"] += net
    game["plays"] += 1

    day_key = now_dt().strftime("%Y-%m-%d")
    day_entry = None
    for item in history:
        if item.get("date") == day_key:
            day_entry = item
            break

    if day_entry is None:
        day_entry = {"date": day_key, "house_profit": 0, "wagered": 0, "paid_out": 0}
        history.append(day_entry)

    day_entry["house_profit"] += net
    day_entry["wagered"] += wager
    day_entry["paid_out"] += payout

    if len(history) > 60:
        casino_profit["history"] = history[-60:]

    if user_id is not None:
        stats_root = data.setdefault("casino_user_stats", {})
        player = stats_root.setdefault(str(user_id), {
            "wagered": 0,
            "paid_out": 0,
            "net": 0,
            "plays": 0,
            "biggest_win": 0,
            "game_counts": {}
        })
        player["wagered"] += wager
        player["paid_out"] += payout
        player["net"] += (payout - wager)
        player["plays"] += 1
        player["biggest_win"] = max(int(player.get("biggest_win", 0)), payout)
        counts = player.setdefault("game_counts", {})
        counts[str(game_name)] = counts.get(str(game_name), 0) + 1

    save_data(data)


def build_profit_bar(percentage, width=24):
    percentage = max(0.0, min(float(percentage), 1.0))
    filled = int(round(width * percentage))
    return "█" * filled + "░" * (width - filled)


def build_profit_sparkline(values):
    blocks = "▁▂▃▄▅▆▇█"
    if not values:
        return "▁"
    max_value = max(max(values), 1)
    chars = []
    for value in values:
        ratio = max(0.0, min(value / max_value, 1.0))
        idx = min(len(blocks) - 1, int(round(ratio * (len(blocks) - 1))))
        chars.append(blocks[idx])
    return "".join(chars)

def resolve_bet_amount(user_id, raw_value):
    if raw_value is None:
        return None
    text = str(raw_value).strip().lower()
    if text in {"all", "max", "allin", "all-in"}:
        return get_user_balance(user_id)
    if text in {"inf", "infinite", "infinity", "∞"}:
        return INFINITE_CASH_VALUE
    return parse_cash_amount(raw_value)


def resolve_game_bet_amount(user_id, raw_value):
    if raw_value is None:
        return None

    text = str(raw_value).strip().lower()
    current_balance = get_user_balance(user_id)

    if text in {"all", "max", "allin", "all-in"}:
        if is_infinite_cash(current_balance):
            return INFINITE_GAME_DISPLAY_BET
        return current_balance

    if text in {"inf", "infinite", "infinity", "∞"}:
        if is_infinite_cash(current_balance):
            return INFINITE_GAME_DISPLAY_BET
        return None

    return parse_cash_amount(raw_value)


def resolve_game_bet_display_amount(user_id, raw_value):
    if raw_value is None:
        return None

    text = str(raw_value).strip().lower()
    current_balance = get_user_balance(user_id)

    if text in {"all", "max", "allin", "all-in", "inf", "infinite", "infinity", "∞"}:
        if is_infinite_cash(current_balance):
            return INFINITE_CASH_VALUE
        return current_balance

    return parse_cash_amount(raw_value)


def generate_crash_point():
    roll = random.random()
    jitter = random.uniform(0.92, 1.08)
    micro = random.uniform(-0.12, 0.12)

    if roll < 0.30:
        crash_point = random.uniform(1.10, 1.95)
    elif roll < 0.62:
        crash_point = random.uniform(1.96, 3.60)
    elif roll < 0.86:
        crash_point = random.uniform(3.61, 6.40)
    elif roll < 0.96:
        crash_point = random.uniform(6.41, 8.90)
    else:
        crash_point = random.uniform(8.91, 10.00)

    crash_point = (crash_point * jitter) + micro
    return max(1.10, min(round(crash_point, 2), 10.0))

async def check_casino_car_pack_role(member, ctx=None):
    try:
        if member is None or member.guild is None:
            return False

        casino_role = member.guild.get_role(CASINO_CAR_PACK_ROLE_ID)
        if casino_role is None:
            return False

        current_balance = get_user_balance(member.id)
        has_role = casino_role in member.roles

        if current_balance >= CASINO_CAR_PACK_THRESHOLD and not has_role:
            await member.add_roles(casino_role, reason="Reached 100 trillion cash")

            role_mention = casino_role.mention if casino_role else "Casino Car Pack"

            embed = discord.Embed(
                title="Casino Car Pack Unlocked",
                description=(
                    f"🏆 {member.mention} has reached **{format_cash(CASINO_CAR_PACK_THRESHOLD)} 💵**\n"
                    f"and unlocked the {role_mention} reward.\n"
                    f"This reward gives a dedicated **5 car pack**."
                ),
                colour=0x57F287,
                timestamp=now_dt()
            )
            embed.set_author(name="GL Customs", icon_url=LOGO_URL)
            embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

            sent_channel_ids = set()

            if ctx and getattr(ctx, "channel", None):
                try:
                    await ctx.channel.send(embed=embed)
                    sent_channel_ids.add(ctx.channel.id)
                except Exception:
                    pass

            try:
                reward_channel = bot.get_channel(REWARD_ANNOUNCEMENT_CHANNEL_ID)
                if reward_channel is None and member.guild:
                    reward_channel = member.guild.get_channel(REWARD_ANNOUNCEMENT_CHANNEL_ID)
                if reward_channel and reward_channel.id not in sent_channel_ids:
                    await reward_channel.send(embed=embed)
                    sent_channel_ids.add(reward_channel.id)
            except Exception:
                pass

            try:
                modlog_channel = bot.get_channel(MODLOG_CHANNEL_ID)
                if modlog_channel is None and member.guild:
                    modlog_channel = member.guild.get_channel(MODLOG_CHANNEL_ID)
                if modlog_channel and modlog_channel.id not in sent_channel_ids:
                    await modlog_channel.send(embed=embed)
            except Exception:
                pass

            return True

        elif current_balance < CASINO_CAR_PACK_THRESHOLD and has_role:
            await member.remove_roles(casino_role, reason="Dropped below 100 trillion cash")
            return False

        return False
    except Exception as e:
        try:
            modlog_channel = bot.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel is None and member and member.guild:
                modlog_channel = member.guild.get_channel(MODLOG_CHANNEL_ID)
            if modlog_channel:
                err = discord.Embed(
                    title="Reward Announcement Error",
                    description=f"Failed to process Casino Car Pack reward for {member.mention if member else 'unknown member'}\n```{e}```",
                    colour=0xE74C3C,
                    timestamp=now_dt()
                )
                err.set_author(name="GL Customs", icon_url=LOGO_URL)
                err.set_footer(text="GL Customs", icon_url=LOGO_URL)
                await modlog_channel.send(embed=err)
        except Exception:
            pass
        return False


def get_user_streaks(user_id):
    data = load_data()
    streaks = data.setdefault("streaks", {})
    return streaks.setdefault(str(user_id), {
        "beg_count": 0,
        "beg_last": None,
        "work_count": 0,
        "work_last": None
    })


def save_user_streaks(user_id, streak_data):
    data = load_data()
    streaks = data.setdefault("streaks", {})
    streaks[str(user_id)] = streak_data
    save_data(data)


def update_claim_streak(user_id, action_name):
    streak_data = get_user_streaks(user_id)
    count_key = f"{action_name}_count"
    last_key = f"{action_name}_last"

    now = now_dt()
    previous_raw = streak_data.get(last_key)
    previous = None
    if previous_raw:
        try:
            previous = datetime.fromisoformat(previous_raw)
        except Exception:
            previous = None

    if previous and (now - previous) <= timedelta(hours=STREAK_RESET_HOURS):
        streak_data[count_key] = int(streak_data.get(count_key, 0)) + 1
    else:
        streak_data[count_key] = 1

    streak_data[last_key] = now.isoformat()
    save_user_streaks(user_id, streak_data)
    return int(streak_data[count_key])


def get_last_weekly_payout():
    data = load_data()
    weekly = data.setdefault("weekly_rewards", {"last_payout": None})
    raw = weekly.get("last_payout")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def set_last_weekly_payout(value):
    data = load_data()
    weekly = data.setdefault("weekly_rewards", {"last_payout": None})
    weekly["last_payout"] = value.isoformat()
    save_data(data)


async def run_weekly_leaderboard_payout():
    last = get_last_weekly_payout()
    if last and (now_dt() - last) < timedelta(days=7):
        return

    top_entries = get_top_leaderboard(limit=3)
    if not top_entries:
        set_last_weekly_payout(now_dt())
        return

    rewarded_users = set()
    payout_lines = []

    primary_guild = bot.guilds[0] if bot.guilds else None

    for index, (user_id, entry) in enumerate(top_entries, start=1):
        reward = WEEKLY_REWARD_AMOUNTS.get(index)
        if not reward or str(user_id) in rewarded_users:
            continue

        rewarded_users.add(str(user_id))
        new_total = add_user_balance(user_id, reward)

        member = primary_guild.get_member(int(user_id)) if primary_guild else None
        if member:
            await check_casino_car_pack_role(member, None)
            display_name = member.display_name
        else:
            display_name = f"User {user_id}"

        payout_lines.append(f"**#{index}** {display_name} — +**{format_cash(reward)} 💵** (Balance: **{new_total:,} 💵**)")

    set_last_weekly_payout(now_dt())

    if payout_lines:
        embed = discord.Embed(
            title="Weekly Leaderboard Payouts",
            description="The weekly rewards have been paid out to the top players.\n\n" + "\n".join(payout_lines),
            colour=0x57F287,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await send_modlog(embed)


def roll_mines_jackpot_bonus(bet_amount):
    if random.random() > MINES_JACKPOT_CHANCE:
        return 0
    minimum = max(MINES_JACKPOT_MIN, int(bet_amount * 2))
    maximum = max(minimum, min(MINES_JACKPOT_MAX, int(bet_amount * 10)))
    return random.randint(minimum, maximum)


def get_cooldown_expiry(user_id, action_name):
    data = load_data()
    cooldowns = data.setdefault("cooldowns", {})
    user_cd = cooldowns.get(str(user_id), {})
    expiry = user_cd.get(action_name)
    if not expiry:
        return None
    try:
        return datetime.fromisoformat(expiry)
    except Exception:
        return None


def set_cooldown_expiry(user_id, action_name, expires_at):
    data = load_data()
    cooldowns = data.setdefault("cooldowns", {})
    user_cd = cooldowns.setdefault(str(user_id), {})
    user_cd[action_name] = expires_at.isoformat()
    save_data(data)


def format_remaining_time(delta):
    total_seconds = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def format_short_cooldown(delta):
    total_seconds = max(0, delta.total_seconds())
    if total_seconds >= 1:
        return f"{total_seconds:.1f}s" if total_seconds < 10 else f"{int(total_seconds)}s"
    return "less than 1s"


async def check_betting_cooldown(ctx, command_name, title):
    expiry = get_cooldown_expiry(ctx.author.id, command_name)
    if expiry and expiry > now_dt():
        remaining = format_short_cooldown(expiry - now_dt())
        embed = discord.Embed(
            title=title,
            description=f"❌ You can use this command again in **{remaining}**.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        message = await ctx.send(embed=embed)
        return False
    return True


def start_betting_cooldown(user_id, command_name):
    set_cooldown_expiry(user_id, command_name, now_dt() + timedelta(seconds=BETTING_COOLDOWN_SECONDS))

def award_game_xp(user_id, command_name, amount=GAME_XP_PER_PLAY):
    data = load_data()
    leaderboard = data.setdefault("leaderboard", {})
    entry = leaderboard.setdefault(str(user_id), {
        "xp": 0,
        "games_played": 0,
        "command_counts": {}
    })

    entry["xp"] += amount
    entry["games_played"] += 1

    command_counts = entry.setdefault("command_counts", {})
    command_counts[command_name] = command_counts.get(command_name, 0) + 1

    save_data(data)


def total_xp_required_to_reach_level(level):
    if level <= 0:
        return 0
    return 50 * level * (level + 1) // 2


def calculate_level_info(total_xp):
    level = 0
    while total_xp >= total_xp_required_to_reach_level(level + 1):
        level += 1

    current_level_floor = total_xp_required_to_reach_level(level)
    next_level_total = total_xp_required_to_reach_level(level + 1)
    xp_into_level = total_xp - current_level_floor
    xp_needed_for_next = next_level_total - total_xp
    xp_for_this_level = next_level_total - current_level_floor

    return {
        "level": level,
        "xp": total_xp,
        "xp_into_level": xp_into_level,
        "xp_needed_for_next": xp_needed_for_next,
        "current_level_floor": current_level_floor,
        "next_level_total": next_level_total,
        "xp_for_this_level": xp_for_this_level
    }


def get_leaderboard_rank(user_id):
    data = load_data()
    leaderboard = data.get("leaderboard", {})

    sorted_users = sorted(
        leaderboard.items(),
        key=lambda item: (
            item[1].get("xp", 0),
            item[1].get("games_played", 0)
        ),
        reverse=True
    )

    for index, (uid, _) in enumerate(sorted_users, start=1):
        if str(uid) == str(user_id):
            return index
    return None


def get_top_leaderboard(limit=10):
    data = load_data()
    leaderboard = data.get("leaderboard", {})

    return sorted(
        leaderboard.items(),
        key=lambda item: (
            item[1].get("xp", 0),
            item[1].get("games_played", 0)
        ),
        reverse=True
    )[:limit]


def serialise_bool(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "none"


def save_lock_state(guild_id, channel_id, send_messages_value):
    data = load_data()
    lock_saved = data.setdefault("lock_saved", {})
    guild_locks = lock_saved.setdefault(str(guild_id), {})
    guild_locks[str(channel_id)] = serialise_bool(send_messages_value)
    save_data(data)


def get_lock_state(guild_id, channel_id):
    data = load_data()
    guild_locks = data.get("lock_saved", {}).get(str(guild_id), {})
    if str(channel_id) not in guild_locks:
        return None, False
    return guild_locks[str(channel_id)], True


def delete_lock_state(guild_id, channel_id):
    data = load_data()
    lock_saved = data.setdefault("lock_saved", {})
    guild_locks = lock_saved.get(str(guild_id), {})
    if str(channel_id) in guild_locks:
        del guild_locks[str(channel_id)]
        if not guild_locks:
            lock_saved.pop(str(guild_id), None)
        save_data(data)


def save_lockdown_state(guild_id, channel_states):
    data = load_data()
    lockdown_saved = data.setdefault("lockdown_saved", {})
    serialised = {str(cid): serialise_bool(val) for cid, val in channel_states.items()}
    lockdown_saved[str(guild_id)] = serialised
    save_data(data)


def get_lockdown_state(guild_id):
    data = load_data()
    lockdown_saved = data.get("lockdown_saved", {})
    if str(guild_id) not in lockdown_saved:
        return {}, False
    return lockdown_saved[str(guild_id)], True


def delete_lockdown_state(guild_id):
    data = load_data()
    lockdown_saved = data.setdefault("lockdown_saved", {})
    if str(guild_id) in lockdown_saved:
        del lockdown_saved[str(guild_id)]
        save_data(data)

# =========================================================
# HELPERS
# =========================================================
async def delete_messages_later(messages, delay=10):
    await asyncio.sleep(delay)
    for message in messages:
        if message is None:
            continue
        try:
            await message.delete()
        except Exception:
            pass


class RiskConfirmView(discord.ui.View):
    def __init__(self, ctx, title, timeout_seconds=CONFIRM_TIMEOUT_SECONDS):
        super().__init__(timeout=timeout_seconds)
        self.ctx = ctx
        self.title = title
        self.result = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            try:
                await interaction.response.send_message(
                    "❌ Only the person who used this command can respond to this confirmation.",
                    ephemeral=True
                )
            except Exception:
                pass
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        for child in self.children:
            child.disabled = True

        embed = build_case_embed(
            self.title,
            "✅ Action confirmed.",
            0x2ECC71
        )

        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception:
            pass

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        for child in self.children:
            child.disabled = True

        embed = build_case_embed(
            self.title,
            "❌ Action cancelled.",
            0xE74C3C
        )

        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception:
            pass

        self.stop()

    async def on_timeout(self):
        if self.result is not None:
            return

        self.result = False
        for child in self.children:
            child.disabled = True

        embed = build_case_embed(
            self.title,
            "❌ Action cancelled. Confirmation timed out.",
            0xE74C3C
        )

        try:
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception:
            pass


async def confirm_action(ctx, title="Confirm Action", prompt_text="This is a dangerous action."):
    embed = build_case_embed(
        title,
        f"⚠️ {prompt_text}\n\nPlease choose **Confirm** or **Cancel** within **{CONFIRM_TIMEOUT_SECONDS} seconds**.",
        0xF1C40F
    )

    view = RiskConfirmView(ctx, title, timeout_seconds=CONFIRM_TIMEOUT_SECONDS)
    prompt_message = await ctx.send(embed=embed, view=view)
    view.message = prompt_message

    await view.wait()

    asyncio.create_task(delete_messages_later(
        [prompt_message],
        delay=CONFIRM_CLEANUP_DELAY_SECONDS
    ))

    return bool(view.result)


def has_regular_member_permission(member):
    if member.guild.owner_id == member.id:
        return True
    role_ids = {role.id for role in member.roles}
    return (
        REGULAR_MEMBER_ROLE_ID in role_ids
        or SECURITY_TEAM_ROLE_ID in role_ids
        or INFRASTRUCTURE_ROLE_ID in role_ids
    )


def has_security_permission(member):
    if member.guild.owner_id == member.id:
        return True
    return any(role.id == SECURITY_TEAM_ROLE_ID for role in member.roles)


def has_infrastructure_permission(member):
    if member.guild.owner_id == member.id:
        return True
    if member.id == OWNER_ID:
        return True
    return any(role.id == INFRASTRUCTURE_ROLE_ID for role in member.roles)


def has_security_or_infrastructure_permission(member):
    if member.guild.owner_id == member.id:
        return True
    role_ids = {role.id for role in member.roles}
    return (
        SECURITY_TEAM_ROLE_ID in role_ids
        or INFRASTRUCTURE_ROLE_ID in role_ids
    )


def has_role_command_permission(member):
    if member.guild.owner_id == member.id:
        return True
    role_ids = {role.id for role in member.roles}
    return (
        SECURITY_TEAM_ROLE_ID in role_ids
        or INFRASTRUCTURE_ROLE_ID in role_ids
    )


def has_role_command_bypass(member):
    if member.guild.owner_id == member.id:
        return True
    return member.id in ROLE_COMMAND_BYPASS_USER_IDS


def has_rolestrip_permission(member):
    if member.guild.owner_id == member.id:
        return True
    role_ids = {role.id for role in member.roles}
    return (
        SECURITY_TEAM_ROLE_ID in role_ids
        or INFRASTRUCTURE_ROLE_ID in role_ids
    )


def can_moderate(author, target):
    if target.id == author.guild.owner_id:
        return False, "❌ You cannot use this on the server owner."
    if author.id != author.guild.owner_id and target.top_role.position >= author.top_role.position:
        return False, "❌ You cannot use this on someone with an equal or higher top role."
    return True, None


def get_staff_cap_position(guild):
    security_role = guild.get_role(SECURITY_TEAM_ROLE_ID)
    infrastructure_role = guild.get_role(INFRASTRUCTURE_ROLE_ID)

    positions = [r.position for r in (security_role, infrastructure_role) if r is not None]
    if not positions:
        return None

    return min(positions)


def role_lookup_case_insensitive(guild, role_name):
    if role_name is None:
        return None

    raw = str(role_name).strip()
    if not raw:
        return None

    mention_match = re.fullmatch(r"<@&(\d+)>", raw)
    if mention_match:
        return guild.get_role(int(mention_match.group(1)))

    if raw.isdigit():
        return guild.get_role(int(raw))

    target = raw.lower()

    for role in guild.roles:
        if role.name.lower() == target:
            return role

    for role in guild.roles:
        if role.name.lower() == target.lstrip("@"):
            return role

    return None


def is_dangerous_role(role):
    perms = role.permissions
    return (
        role.id in BLOCKED_ROLE_IDS
        or perms.administrator
        or perms.manage_guild
        or perms.manage_roles
        or perms.ban_members
        or perms.kick_members
        or perms.manage_channels
        or perms.manage_messages
        or perms.mention_everyone
        or perms.moderate_members
    )




def parse_user_id_input(raw_value):
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    match = re.fullmatch(r"<@!?(\d+)>", text)
    if match:
        return int(match.group(1))

    if text.isdigit():
        return int(text)

    return None


async def resolve_ban_target(ctx, target_input):
    if target_input is None:
        return None, None, "missing"

    text = str(target_input).strip()
    if not text:
        return None, None, "missing"

    member = None
    try:
        member = await commands.MemberConverter().convert(ctx, text)
    except commands.BadArgument:
        member = None

    if member is not None:
        return member, member.id, "member"

    user_id = parse_user_id_input(text)
    if user_id is None:
        return None, None, "invalid"

    member = ctx.guild.get_member(user_id)
    if member is not None:
        return member, user_id, "member"

    return None, user_id, "id_only"

async def resolve_member_query(ctx, query: str):
    if query is None:
        return None

    text_query = str(query).strip()
    if not text_query:
        return None

    try:
        return await commands.MemberConverter().convert(ctx, text_query)
    except commands.BadArgument:
        pass

    member_id = parse_user_id_input(text_query)
    if member_id is not None:
        member = ctx.guild.get_member(member_id)
        if member:
            return member

    lowered = text_query.casefold()

    exact_matches = []
    partial_matches = []

    for member in ctx.guild.members:
        username = str(member.name).casefold()
        display_name = str(member.display_name).casefold()
        global_name = str(member.global_name).casefold() if getattr(member, "global_name", None) else ""

        if lowered in {username, display_name, global_name}:
            exact_matches.append(member)
            continue

        if lowered in username or lowered in display_name or (global_name and lowered in global_name):
            partial_matches.append(member)

    if exact_matches:
        return exact_matches[0]
    if partial_matches:
        return partial_matches[0]
    return None

def parse_duration(duration_text):
    match = re.fullmatch(r"(\d+)([smhd])", duration_text.lower().strip())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return None


def normalise_saved_bool(value):
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "none":
        return None
    return None


# =========================================================
# ROLE REQUEST HELPERS
# =========================================================
EXCLUDED_ROLE_NAMES = {
    "member",
    "blacklisted",
    "bots",
    "blacklisted bots",
    "giveaway winner",
    "retired management",
    "wip notified",
    "media notified",
    "giveaway notified",
    "muted",
}

ROLE_REQUEST_PAGE_SIZE = 25
ROLE_REQUEST_HIGHEST_ROLE_NAME = "assistant management"


def normalise_role_request_name(name):
    return " ".join(str(name).split()).strip().casefold()


def is_excluded_role_request_name(role_name):
    normalised = normalise_role_request_name(role_name)
    if normalised in EXCLUDED_ROLE_NAMES:
        return True
    if "bot" in normalised or "notify" in normalised or "blacklist" in normalised:
        return True
    return False


def get_role_request_cap_position(guild):
    for role in guild.roles:
        if normalise_role_request_name(role.name) == ROLE_REQUEST_HIGHEST_ROLE_NAME:
            return role.position
    return None


def get_requestable_roles(guild, member):
    bot_member = guild.me
    if bot_member is None:
        return []

    bot_top_position = bot_member.top_role.position
    role_request_cap_position = get_role_request_cap_position(guild)
    requestable = []

    for role in guild.roles:
        if role.id == guild.id:
            continue
        if role.managed:
            continue
        if is_excluded_role_request_name(role.name):
            continue
        if role in member.roles:
            continue
        if role.position >= bot_top_position:
            continue
        if role_request_cap_position is not None and role.position > role_request_cap_position:
            continue

        requestable.append(role)

    requestable.sort(key=lambda r: r.position, reverse=True)
    return requestable


def build_role_request_embed(
    requester,
    role,
    approver_text="Pending",
    status_text="Pending Review",
    colour=None,
    case_id=None,
    decision_text=None,
):
    embed_colour = colour
    if embed_colour is None:
        try:
            embed_colour = role.colour.value if getattr(role, "colour", None) and role.colour.value else 0x3498DB
        except Exception:
            embed_colour = 0x3498DB

    embed = discord.Embed(
        title="Role Requested",
        description=decision_text or f"A role has been requested by {requester.mention}.",
        colour=embed_colour,
        timestamp=now_dt()
    )
    embed.set_author(
        name=f"Case: {case_id}" if case_id is not None else "GL Customs",
        icon_url=LOGO_URL
    )
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

    embed.add_field(name="Requester", value=requester.mention, inline=False)
    embed.add_field(name="Decision By", value=approver_text, inline=False)
    embed.add_field(name="Status", value=status_text, inline=False)
    embed.add_field(name="Role", value=f"{role.mention}\n{role.name} | {role.id}", inline=False)

    return embed

# =========================================================
# STYLE / LOGGING
# =========================================================
def build_case_embed(
    title,
    description,
    colour,
    *,
    case_id=None,
    user=None,
    user_id=None,
    staff=None,
    reason=None,
    extra_fields=None
):
    embed = discord.Embed(
        title=title,
        description=description,
        colour=colour,
        timestamp=now_dt()
    )

    embed.set_author(
        name=f"Case: {case_id}" if case_id is not None else "GL Customs",
        icon_url=LOGO_URL
    )
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

    if user is not None:
        embed.add_field(name="Username", value=user.mention, inline=True)
        embed.add_field(name="User ID", value=str(user.id), inline=True)
    elif user_id is not None:
        embed.add_field(name="Username", value=f"<@{int(user_id)}>", inline=True)
        embed.add_field(name="User ID", value=str(int(user_id)), inline=True)

    if reason is not None:
        embed.add_field(name="Reason", value=reason if reason else "None", inline=False)

    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value if value else " ", inline=inline)

    embed.add_field(name="Date Issued", value=now_str(), inline=False)
    return embed


def game_embed(title, description, colour=0x5865F2):
    embed = discord.Embed(
        title=title,
        description=description,
        colour=colour,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs Games", icon_url=LOGO_URL)
    return embed


async def send_game_premessage(ctx, title, first_line=None, second_line=None, colour=0x5865F2):
    first_line = first_line or random.choice([
        "🎰 Loading game...",
        "⚙️ Preparing table...",
        "💰 Checking balance...",
        "🎲 Warming up the game..."
    ])
    second_line = second_line or random.choice([
        "✨ Almost ready...",
        "🎮 Finalising setup...",
        "📡 Syncing result engine...",
        "🃏 Just a second..."
    ])

    embed = discord.Embed(title=title, description=first_line, colour=colour, timestamp=now_dt())
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    message = await ctx.send(embed=embed)
    await asyncio.sleep(0.45)
    embed.description = second_line
    await message.edit(embed=embed)
    return message


async def send_modlog(embed):
    channel = bot.get_channel(MODLOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

# =========================================================
# BACKGROUND TASKS
# =========================================================
@tasks.loop(seconds=30)
async def temp_role_checker():
    data = load_data()
    temp_roles = data.get("temp_roles", {})
    changed = False
    current_time = now_dt()

    for user_id, entries in list(temp_roles.items()):
        remaining = []

        for entry in entries:
            try:
                expires_at = datetime.fromisoformat(entry["expires_at"])
            except Exception:
                changed = True
                continue

            if expires_at > current_time:
                remaining.append(entry)
                continue

            guild = bot.get_guild(int(entry["guild_id"]))
            if guild is None:
                changed = True
                continue

            member = guild.get_member(int(user_id))
            role = guild.get_role(int(entry["role_id"]))

            if member and role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Temporary role expired")
                except Exception:
                    pass

            changed = True

        if remaining:
            temp_roles[user_id] = remaining
        else:
            temp_roles.pop(user_id, None)

    if changed:
        save_temp_roles(temp_roles)


@tasks.loop(hours=1)
async def weekly_leaderboard_payouts():
    await run_weekly_leaderboard_payout()


@weekly_leaderboard_payouts.before_loop
async def before_weekly_leaderboard_payouts():
    await bot.wait_until_ready()


@temp_role_checker.before_loop
async def before_temp_role_checker():
    await bot.wait_until_ready()

# =========================================================
# EVENTS
# =========================================================
@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    if not temp_role_checker.is_running():
        temp_role_checker.start()
    if not weekly_leaderboard_payouts.is_running():
        weekly_leaderboard_payouts.start()


@bot.event
async def on_member_join(member):
    if is_globally_banned(member.id):
        info = get_global_ban(member.id)
        reason = info["reason"] if info else "Global ban"
        try:
            await member.guild.ban(member, reason=f"Auto GBAN | {reason}")
        except (discord.Forbidden, discord.HTTPException):
            pass
        return

    created_at = member.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    account_age = (now_dt() - created_at).days

    if account_age < ALT_ACCOUNT_DAYS:
        embed = build_case_embed(
            "Possible Alt Account",
            f"{member.mention} joined with a **very new account**.",
            0xE67E22,
            user=member,
            extra_fields=[
                ("Account Age", f"{account_age} day(s)", True)
            ]
        )

        alt_channel = bot.get_channel(ALT_ACCOUNT_CHANNEL_ID)
        if alt_channel:
            await alt_channel.send(embed=embed)

# =========================================================
# BASIC
# =========================================================
@bot.command()
async def ping(ctx):
    embed = build_case_embed(
        "Ping",
        "Bot latency check completed.",
        0x2ECC71,
        user=ctx.author,
        extra_fields=[
            ("Gateway", f"{round(bot.latency * 1000, 2)}ms", True)
        ]
    )
    await ctx.send(embed=embed)


@bot.command(name="payment")
async def payment(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed(
            "Payment Options",
            "❌ You do not have permission to use this command.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    embed = build_case_embed(
        "Payment Options",
        "Here are the available payment methods for GL Customs.",
        0x3498DB,
        extra_fields=[
            ("PayPal", "Available", True),
            ("Revolut", "Available", True),
            ("Wise", "Available", True),
            ("Note", "Please contact <@793613955003318273> if you need payment details.", False)
        ]
    )
    await ctx.send(embed=embed)


@bot.command(name="botinfo")
async def botinfo(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed(
            "Bot Information",
            "❌ You do not have permission to use this command.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    embed = build_case_embed(
        "Bot Information",
        "This bot is built to support GL Customs with moderation, utility features and server engagement.",
        0x3498DB,
        extra_fields=[
            ("Moderation", "Handles warnings, bans, global bans, timeouts, locks and case logging.", False),
            ("Role Management", "Can give, remove and temporarily assign roles.", False),
            ("Utility", "Supports purge, slowmode, audit logging and case lookup.", False),
            ("Fun / Community", "Games, random commands and leaderboard system.", False),
        ]
    )
    await ctx.send(embed=embed)


@bot.command(name="leaderboard")
async def leaderboard(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed(
            "Leaderboard",
            "❌ You do not have permission to use this command.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    data = load_data()
    balances = data.get("balances", {})
    cash_entries = sorted(
        [(uid, int(amount)) for uid, amount in balances.items()],
        key=lambda item: item[1],
        reverse=True
    )[:10]

    user_balance = get_user_balance(ctx.author.id)
    cash_rank = None
    sorted_all_balances = sorted(
        [(uid, int(amount)) for uid, amount in balances.items()],
        key=lambda item: item[1],
        reverse=True
    )
    for idx, (uid, _) in enumerate(sorted_all_balances, start=1):
        if str(uid) == str(ctx.author.id):
            cash_rank = idx
            break

    player_stats = get_casino_user_stats(ctx.author.id)
    fav_game = "None"
    game_counts = player_stats.get("game_counts", {})
    if game_counts:
        fav_game = max(game_counts.items(), key=lambda item: item[1])[0]

    top_lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for index, (user_id, balance_amount) in enumerate(cash_entries, start=1):
        member = ctx.guild.get_member(int(user_id))
        display_name = member.display_name if member else f"User {user_id}"
        badge = medals.get(index, f"**{index}.**")
        top_lines.append(f"{badge} {display_name} — **{format_cash(balance_amount)} 💵**")

    embed = discord.Embed(
        title="Casino Leaderboard",
        description=(
            f"**Your Cash Rank:** {'#' + str(cash_rank) if cash_rank else 'Unranked'}\n"
            f"**Your Balance:** {format_cash(user_balance)} 💵\n"
            f"**Casino Games Played:** {player_stats.get('plays', 0)}\n"
            f"**Favourite Casino Game:** {fav_game}\n"
            f"**Biggest Win:** {format_cash(player_stats.get('biggest_win', 0))} 💵"
        ),
        colour=0x5865F2,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs Casino", icon_url=LOGO_URL)
    embed.add_field(
        name="Top 10 Richest Players",
        value="\n".join(top_lines) if top_lines else "No balance data yet.",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name="rank")
async def rank(ctx, member: discord.Member = None):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed("Rank", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    member = member or ctx.author
    stats = get_user_game_stats(member.id)
    level_info = calculate_level_info(stats.get("xp", 0))
    rank_position = get_leaderboard_rank(member.id)

    most_played = stats.get("command_counts", {})
    favourite_game = "None"
    if most_played:
        favourite_game = max(most_played.items(), key=lambda item: item[1])[0]

    progress_total = max(level_info["xp_for_this_level"], 1)
    progress_text = f"{level_info['xp_into_level']}/{progress_total} XP"

    embed = build_case_embed(
        "Rank Card",
        f"Rank information for {member.mention}.",
        0x3498DB,
        user=member,
        extra_fields=[
            ("Rank", f"#{rank_position}" if rank_position else "Unranked", True),
            ("Level", str(level_info["level"]), True),
            ("Total XP", str(level_info["xp"]), True),
            ("Progress", progress_text, True),
            ("Games Played", str(stats.get("games_played", 0)), True),
            ("Favourite Game", favourite_game, True),
            ("Next Level In", f"{level_info['xp_needed_for_next']} XP", False),
        ]
    )
    await ctx.send(embed=embed)

# =========================================================
# FUN / GAMES
# =========================================================
TRIVIA_QUESTIONS = [
    {"q": "What year was the first Fast and Furious film released?", "a": "2001"},
    {"q": "Which car brand makes the GT-R?", "a": "Nissan"},
    {"q": "How many sides does a standard dice have?", "a": "6"},
    {"q": "What colour do you get by mixing blue and yellow?", "a": "Green"},
    {"q": "Which planet is known as the Red Planet?", "a": "Mars"},
    {"q": "What does CPU stand for?", "a": "Central Processing Unit"},
    {"q": "Which animal is known as man's best friend?", "a": "Dog"},
    {"q": "What is the capital of Japan?", "a": "Tokyo"},
]

WOULD_YOU_RATHER = [
    "Would you rather own your dream supercar or your dream house?",
    "Would you rather have unlimited fuel for a year or free insurance for life?",
    "Would you rather be able to teleport or pause time?",
    "Would you rather win £10,000 today or £100,000 in 5 years?",
    "Would you rather drive only manual forever or only automatic forever?",
    "Would you rather race on a track or build show cars?",
    "Would you rather lose your phone or your wallet for a week?",
    "Would you rather have perfect memory or never need sleep?",
]

TRUTHS = [
    "What is one thing you always overthink?",
    "What is your most expensive bad habit?",
    "What was your most awkward moment online?",
    "What car would you buy if money did not matter?",
    "What is one thing most people here do not know about you?",
    "What is the worst purchase you ever made?",
]

DARES = [
    "Change your nickname to 'Turbo Potato' for 10 minutes.",
    "Send the last photo in your camera roll to the chat.",
    "Type your next message with your eyes closed.",
    "React with 🔥 to the next five messages you see.",
    "Say your dream car in ALL CAPS.",
    "Use only emojis for your next message.",
]

FORTUNES = [
    "A lucky opportunity is closer than you think.",
    "Today is a good day to take a small risk.",
    "Someone will notice your effort soon.",
    "Your next idea will be better than your last one.",
    "Good news will arrive when you least expect it.",
    "Patience will save you from a bad choice.",
    "A bold decision will pay off later.",
    "You are due a win soon.",
]

COMPLIMENTS = [
    "You have elite taste.",
    "You make this server better.",
    "You have main character energy.",
    "You are far cooler than you realise.",
    "You have immaculate vibes.",
    "You are built for success.",
    "You bring good energy wherever you go.",
    "You are genuinely underrated.",
]

ANIMALS = ["Dog", "Cat", "Fox", "Wolf", "Tiger", "Bear", "Owl", "Falcon", "Shark", "Panda"]
FOODS = ["Pizza", "Burger", "Tacos", "Sushi", "Steak", "Pasta", "Curry", "Burrito", "Fries", "Donuts"]
CARS = ["Nissan GT-R", "Toyota Supra", "BMW M3", "Audi RS6", "Porsche 911", "Ford Mustang", "Lamborghini Huracán", "McLaren 720S"]
COLOURS = ["Red", "Blue", "Black", "White", "Purple", "Green", "Orange", "Silver", "Gold", "Navy"]
COUNTRIES = ["Japan", "Germany", "United Kingdom", "Italy", "Spain", "Canada", "Brazil", "Australia", "Norway", "UAE"]
EMOJIS = ["🔥", "🚗", "⚡", "🏁", "🎮", "🎲", "👑", "💎", "😎", "🚀"]
SUPERPOWERS = ["Teleportation", "Time travel", "Invisibility", "Super speed", "Flight", "Mind reading", "Shape shifting", "Healing"]
MYSTERY_BOX_ITEMS = ["A turbo kit", "£100", "A banana", "A brand new alloy wheel", "An empty box", "A lucky key", "A PS5", "A packet of crisps"]
SCRAMBLE_WORDS = ["engine", "garage", "turbo", "customs", "discord", "racecar", "mechanic", "spoiler"]
MEME_IDEAS = [
    "Group chat goes silent the second someone says 'who scratched my car?'.",
    "When you say 'I am only going out for one drink' and suddenly it is daylight.",
    "POV: you open your banking app right after a night out and immediately regret everything.",
    "When someone says 'be honest' and then gets offended by the honest answer.",
    "That one friend who is always '2 minutes away' but has not even left the house.",
    "When the Wi-Fi cuts out and the whole house suddenly starts acting like it is the end times.",
    "Me acting unbothered after sending a risky message and then watching for the reply instantly.",
    "When you agree to a quick plan and it somehow turns into a full mission.",
    "That moment you hear 'we need to talk' and your whole body takes a screenshot.",
    "When someone starts telling a story and you realise halfway through that you are the villain in it.",
]
FAKE_ACHIEVEMENTS = [
    "Unlocked: Weekend Warrior",
    "Unlocked: Keyboard Mechanic",
    "Unlocked: Lucky Guess",
    "Unlocked: Turbo Brain",
    "Unlocked: Chaos Controller",
    "Unlocked: Meme Machine",
    "Unlocked: Pit Lane Legend",
]

EIGHTBALL_RESPONSES = [
    "Everything points to **yes** right now. I would back it.",
    "That is looking like a **strong yes** from here.",
    "There is a good chance this goes in your favour.",
    "I would say **probably yes**, but do not get careless.",
    "The signs are positive, just be patient with it.",
    "This feels like it will work out, just not instantly.",
    "You are on the right track. Keep going.",
    "It is possible, but your timing needs to be better.",
    "That one is still uncertain. Give it a bit more time.",
    "The result is mixed at the moment. Ask again later.",
    "Not enough is lined up yet for a clear answer.",
    "This could go either way, so do not rely on luck alone.",
    "It is **not looking great** right now.",
    "I would not count on that happening soon.",
    "The answer is leaning **no** at the moment.",
    "That is a **hard no** from the 8 ball.",
    "Absolutely not. Save yourself the stress.",
    "There is too much against you for that one right now.",
    "You might get the outcome you want, but only after a setback.",
    "Yes, but only if you actually follow through properly.",
    "The odds are decent, but do not force it.",
    "This one looks promising from where I am sitting.",
    "It is trending in the right direction.",
    "You may need one more good move before that becomes a yes.",
    "I would stay patient, but it is not a bad shout.",
    "That outcome is possible, though not guaranteed.",
    "Right now the answer feels delayed, not denied.",
    "Too much noise around this one for a clean answer.",
    "You are better off waiting before acting on that.",
    "It is a yes, but not the easy kind."
]


@bot.command(name="games")
async def games(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Games", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed(
        "🎮 Game Commands",
        "\n".join([
            "`!coinflip`",
            "`!roll [sides]`",
            "`!8ball <question>`",
            "`!choose option 1 | option 2 | option 3`",
            "`!rps <rock/paper/scissors>`",
            "`!guess <1-10>`",
            "`!number <min> <max>`",
            "`!slots [bet]`",
            "`!roulette [bet] [red/black/green/0-36]`",
            "`!crash [bet]`",
            "`!rocket [bet]`",
            "`!dice [bet] [high/low]`",
            "`!baccarat [bet] [player/banker/tie]`",
            "`!plinko [bet]`",
            "`!mines <bet> <mines>` / `!mine <bet> <mines>`",
            "`!bj <bet>`",
            "`!chess [bet]`",
            "`!balance [@user]` / `!bal [@user]`",
            "`!beg`",
            "`!work`",
            "`!give @user <amount>`",
            "`!rewards`",
            "`!rate <something>`",
            "`!ship @user [@user]`",
            "`!trivia`",
            "`!fortune`",
            "`!compliment [@user]`",
            "`!wyr`",
            "`!truth`",
            "`!dare`",
            "`!emoji`",
            "`!colourpick`",
            "`!animalpick`",
            "`!foodpick`",
            "`!carpick`",
            "`!countrypick`",
            "`!superpower`",
            "`!mysterybox`",
            "`!race @user`",
            "`!battle @user`",
            "`!reverse <text>`",
            "`!say <text>`",
            "`!fact`",
            "`!memeidea`",
            "`!scramble`",
            "`!achievement`",
            "`!namegen`",
            "`!leaderboard`",
            "`!mystats [@user]`",
            "`!rank [@user]`",
        ])
    )
    await ctx.send(embed=embed)


@bot.command(name="coinflip", aliases=["flip", "coin"])
async def coinflip(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Coin Flip", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    result = random.choice(["Heads", "Tails"])
    extras = [
        "Luck picked your side today.",
        "The coin has spoken.",
        "That one landed clean.",
        "Simple result, big meaning.",
        "Chance made the call."
    ]
    embed = game_embed("🪙 Coin Flip", f"{ctx.author.mention} flipped **{result}**.\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)


@bot.command(name="roll")
async def roll(ctx, sides: int = 6):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Dice Roll", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if sides < 2 or sides > 1000:
        embed = game_embed("Dice Roll", "❌ Choose a number of sides between **2** and **1000**.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    result = random.randint(1, sides)
    extras = [
        "That is a strong roll.",
        "The dice were in your favour there.",
        "Not bad at all.",
        "The dice had something to say.",
        "Solid result from the dice."
    ]
    embed = game_embed("🎲 Dice Roll", f"{ctx.author.mention} rolled a **{result}** on a **d{sides}**.\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)


EIGHTBALL_TOPIC_KEYWORDS = {
    "weather": ["weather", "rain", "raining", "sun", "sunny", "hot", "warm", "cold", "storm", "wind", "windy", "snow", "forecast", "tomorrow", "cloud", "cloudy"],
    "money": ["money", "cash", "rich", "paid", "pay", "profit", "win", "winnings", "bet", "gamble", "casino", "buy", "sell", "price", "afford", "debt"],
    "relationship": ["love", "relationship", "dating", "date", "boyfriend", "girlfriend", "crush", "ex", "marry", "married", "partner", "text", "kiss", "romance"],
    "work": ["job", "work", "boss", "manager", "career", "interview", "promotion", "hired", "hire", "office", "business", "client", "project", "shift", "school", "exam", "test", "pass", "fail"],
    "car": ["car", "cars", "engine", "turbo", "garage", "mechanic", "wrap", "mod", "mods", "wheel", "wheels", "tyre", "tires", "exhaust", "drift", "race", "racing"],
    "gaming": ["game", "gaming", "rank", "ranked", "match", "lobby", "cod", "fortnite", "gta", "fifa", "minecraft", "server", "play"],
    "travel": ["travel", "trip", "holiday", "flight", "airport", "hotel", "drive", "driving", "journey", "road", "abroad", "vacation"],
    "health": ["health", "ill", "sick", "better", "worse", "heal", "healing", "sleep", "tired", "energy", "stress", "anxiety", "gym", "workout"],
}

EIGHTBALL_TOPIC_OPENERS = {
    "weather": [
        "On the weather front,", "Looking at tomorrow's forecast vibe,", "For the sky side of it,", "Weather-wise,",
        "As far as tomorrow goes,", "For the forecast angle,", "If we are talking weather,", "From a weather point of view,"
    ],
    "money": [
        "On the money side of it,", "Financially speaking,", "If this is about cash,", "From a profit point of view,",
        "On the betting side,", "For your wallet,", "If the question is about money,", "Cash-wise,"
    ],
    "relationship": [
        "On the love side of it,", "Relationship-wise,", "If this is about your heart,", "Romantically speaking,",
        "On the dating front,", "If this is about them,", "Emotionally speaking,", "For the relationship angle,"
    ],
    "work": [
        "For work and study,", "Career-wise,", "On the job front,", "If this is about school or work,",
        "Professionally speaking,", "For the practical side of it,", "Looking at the effort side,", "On the work path,"
    ],
    "car": [
        "On the car side of it,", "Mechanically speaking,", "If this is about the motor,", "Garage wisdom says,",
        "From a car scene point of view,", "For the vehicle side of things,", "If we are talking mods and motors,", "On the automotive front,"
    ],
    "gaming": [
        "On the gaming side,", "For this match-up,", "If we are talking game luck,", "The lobby is saying,",
        "From a ranked point of view,", "For the next session,", "Controller wisdom says,", "On the server side of things,"
    ],
    "travel": [
        "For travel plans,", "On the trip side of it,", "If this is about getting away,", "Journey-wise,",
        "For the holiday angle,", "From a travel point of view,", "On the road or flight front,", "If bags are involved,"
    ],
    "health": [
        "For your wellbeing,", "On the health side,", "If this is about how you feel,", "Body and mind wise,",
        "Looking at your energy,", "For the recovery angle,", "On the wellbeing front,", "If it is about feeling better,"
    ],
    "general": [
        "Reading the overall vibe,", "From where I am sitting,", "The 8 ball says,", "Looking at the signs,",
        "If I had to call it,", "From the feel of it,", "Right now,", "Going off the energy,"
    ],
}

EIGHTBALL_TOPIC_ADVICE = {
    "weather": [
        "still keep a backup plan handy", "take layers anyway", "do not trust one perfect forecast", "be ready for a last-minute weather plot twist",
        "keep an eye on the sky", "do not leave the house unprepared"
    ],
    "money": [
        "do not get reckless with it", "protect the bag first", "keep your expectations sensible", "stay sharp with your timing",
        "make the smart move, not the flashy one", "do not risk more than you can afford to laugh about"
    ],
    "relationship": [
        "watch their actions more than their words", "do not chase what is not matching your energy", "keep your dignity in it", "let it breathe a bit",
        "stay honest and you will see it clearly", "do not fill in the blanks for them"
    ],
    "work": [
        "preparation matters more than luck here", "do the boring bits properly", "stay sharp and follow through", "consistency will matter a lot here",
        "do not leave it all to chance", "a clean plan will help more than hope"
    ],
    "car": [
        "do not ignore the boring checks first", "make sure the work is done properly", "do not cheap out on the important bits", "check the details before committing",
        "the right parts matter more than hype", "make sure the plan matches the budget"
    ],
    "gaming": [
        "do not throw by getting overconfident", "play sharp, not desperate", "stay focused and do not tilt", "do not rely on randoms to save you",
        "keep your head and play the smart move", "one good decision will matter more than ten lucky ones"
    ],
    "travel": [
        "plan for one annoying delay", "check the details twice", "leave yourself buffer time", "travel rewards being organised",
        "keep the essentials close", "do not wing the important bits"
    ],
    "health": [
        "be sensible with yourself", "do not ignore what your body is telling you", "rest will probably help more than pushing through", "take care of the basics properly",
        "go easy where you need to", "look after yourself first"
    ],
    "general": [
        "do not force an answer that is not ready", "timing matters here", "a little patience will tell you more", "keep your head clear and watch what happens next",
        "do not rush yourself into the wrong move", "let the next sign show up"
    ],
}

EIGHTBALL_OUTCOME_LINES = {
    "yes": [
        "**Yes**.", "**Strong yes**.", "**Leaning yes**.", "**Looks likely**.", "**Good chance**.", "**Very possible**.",
        "**I would back it**.", "**Positive signs**.", "**The odds look decent**.", "**It is heading the right way**."
    ],
    "maybe": [
        "**Maybe**.", "**Unclear right now**.", "**Too close to call**.", "**Could go either way**.", "**Not settled yet**.",
        "**Ask again later**.", "**Possible, but messy**.", "**The signs are mixed**.", "**It is still forming**.", "**Leaning neutral**."
    ],
    "no": [
        "**No**.", "**Hard no**.", "**Not likely**.", "**Probably not**.", "**Bad odds**.", "**I would not back it**.",
        "**Leaning no**.", "**Very doubtful**.", "**That path looks blocked**.", "**The signs are rough**."
    ],
}

EIGHTBALL_TONE_LINES = {
    "yes": [
        "The signs are lining up.", "Momentum is on your side.", "That path looks open.", "It has the right kind of pull behind it.",
        "That feels more likely than not.", "It is giving green-light energy.", "That one has decent odds.", "This looks promising from here."
    ],
    "maybe": [
        "The timing still feels messy.", "There is too much noise around it.", "A few things still need to move.", "It does not feel locked in yet.",
        "That answer is still forming.", "I would not call this one early.", "It could swing with one small change.", "This still needs a clearer sign."
    ],
    "no": [
        "The signs are not kind to that right now.", "There is too much pushing against it.", "The odds feel rough on this one.", "It is giving more resistance than support.",
        "That looks off for now.", "I do not like the feel of it.", "That one looks like a miss at the moment.", "This lane looks blocked right now."
    ],
}

EIGHTBALL_FOLLOWUPS = {
    "yes": [
        "Do not overthink it now.", "Just do your part and let it land.", "Keep your timing clean.", "Now is the time to follow through.",
        "A bit of patience will help it stick.", "Move with confidence, not panic."
    ],
    "maybe": [
        "Give it a little more time.", "Wait before you commit to that answer.", "You need a clearer sign first.", "Check again when things settle.",
        "Do not rush the outcome.", "Watch what changes next."
    ],
    "no": [
        "I would not force it.", "Best save yourself the headache.", "Leave that one alone for now.", "You are better off changing course.",
        "Wait before putting more into it.", "That is one to step back from."
    ],
}


EIGHTBALL_CHEEKY_CHANCE = 0.08
EIGHTBALL_SENSITIVE_KEYWORDS = {
    "black", "white", "asian", "arab", "latino", "latina", "race", "racist", "ethnicity", "ethnic",
    "gay", "lesbian", "bi", "bisexual", "trans", "transgender", "queer", "straight",
    "muslim", "christian", "jewish", "hindu", "sikh", "religion", "religious",
    "disabled", "disability", "autism", "autistic", "adhd", "depressed", "depression"
}

EIGHTBALL_CHEEKY_LINES = {
    "yes": [
        "Try not to ruin the good odds by panicking.",
        "That is the kind of answer people get when they stop winging it for five minutes.",
        "For once, the chaos might actually work in your favour.",
        "Do not celebrate too early and fumble it at the finish line.",
        "It is looking good, which is brave considering the question."
    ],
    "maybe": [
        "Even the 8 ball is asking for a minute with that one.",
        "That depends how committed you are to chaos, really.",
        "I would love to be dramatic, but this one is annoyingly undecided.",
        "The answer is wobbling because your plan probably is too.",
        "This has strong 'could be amazing, could be a mess' energy."
    ],
    "no": [
        "Let us not pretend that was ever a sensible plan.",
        "That one looks like a future regret in the making.",
        "Respectfully, the odds are not exactly worshipping you here.",
        "I would blame bad luck, but this one might just be a bad idea.",
        "The universe read that question and sighed a bit."
    ],
}


def detect_eightball_topic(question_text):
    lowered = question_text.lower()
    best_topic = "general"
    best_score = 0
    for topic, keywords in EIGHTBALL_TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def extract_eightball_focus(question_text, topic):
    lowered = question_text.lower()
    checks = {
        "weather": [
            ("hot", "the weather staying on the hot side"), ("warm", "the weather leaning warm"),
            ("cold", "the weather turning cold"), ("rain", "rain showing up"), ("raining", "rain showing up"),
            ("storm", "a storm rolling in"), ("wind", "the wind picking up"), ("snow", "snow showing up"),
            ("sun", "some proper sunshine")
        ],
        "money": [
            ("rich", "you ending up richer from it"), ("paid", "money landing in your pocket"), ("pay", "the payment coming through"),
            ("profit", "it turning a profit"), ("win", "you winning from it"), ("bet", "that bet paying off"),
            ("buy", "that purchase being worth it"), ("sell", "that sale going through")
        ],
        "relationship": [
            ("love", "love moving in your favour"), ("relationship", "that relationship working out"), ("date", "that date going well"),
            ("crush", "your crush noticing you"), ("ex", "that ex situation changing"), ("text", "that text actually leading somewhere")
        ],
        "work": [
            ("job", "that job situation going your way"), ("interview", "that interview landing well"), ("promotion", "a promotion being close"),
            ("hired", "you getting hired"), ("exam", "the exam going in your favour"), ("test", "the test working out for you"),
            ("pass", "you passing it"), ("fail", "you avoiding a fail here")
        ],
        "car": [
            ("car", "that car situation working out"), ("engine", "the engine holding up how you want"), ("turbo", "the turbo idea being a good shout"),
            ("garage", "the garage job going smoothly"), ("mechanic", "the mechanic sorting it properly"), ("wrap", "that wrap looking right"),
            ("mod", "that mod being worth it"), ("race", "the race going your way")
        ],
        "gaming": [
            ("rank", "your rank improving from this"), ("win", "you coming away with the win"), ("lose", "you avoiding a loss here"),
            ("match", "the match going in your favour"), ("lobby", "that lobby treating you kindly"), ("server", "the server not betraying you for once")
        ],
        "travel": [
            ("trip", "the trip going smoothly"), ("holiday", "the holiday being worth it"), ("flight", "the flight going the way you want"),
            ("airport", "the airport part not being chaos"), ("hotel", "the hotel being decent"), ("drive", "the drive going cleanly")
        ],
        "health": [
            ("better", "things improving from here"), ("worse", "it not getting worse"), ("sleep", "your sleep improving"),
            ("tired", "your energy picking back up"), ("stress", "the stress easing off"), ("anxiety", "things feeling calmer soon")
        ],
    }
    for key, value in checks.get(topic, []):
        if key in lowered:
            return value
    return {
        "weather": "the weather around that question",
        "money": "the money side of that",
        "relationship": "the relationship side of that",
        "work": "the work side of that",
        "car": "the car side of that",
        "gaming": "the game side of that",
        "travel": "that travel plan",
        "health": "how that is going for you",
        "general": "that situation",
    }.get(topic, "that situation")


def pick_eightball_outcome(question_text):
    lowered = question_text.lower()
    yes_bias = ["will", "can", "should", "worth", "good", "best", "pass", "win", "rich", "hot", "sunny", "better"]
    no_bias = ["bad", "lose", "fail", "cold", "rain", "worse", "broke", "crash"]
    score = 0
    if any(word in lowered for word in yes_bias):
        score += 1
    if any(word in lowered for word in no_bias):
        score -= 1
    roll = random.random()
    if score >= 1:
        return "yes" if roll < 0.55 else "maybe" if roll < 0.83 else "no"
    if score <= -1:
        return "no" if roll < 0.55 else "maybe" if roll < 0.83 else "yes"
    return "yes" if roll < 0.38 else "maybe" if roll < 0.70 else "no"


def is_sensitive_eightball_question(question_text):
    lowered = f" {question_text.lower()} "
    for keyword in EIGHTBALL_SENSITIVE_KEYWORDS:
        if f" {keyword} " in lowered:
            return True
    return False


def build_eightball_answer(question_text):
    topic = detect_eightball_topic(question_text)
    focus = extract_eightball_focus(question_text, topic)
    outcome = pick_eightball_outcome(question_text)

    short_outcome_lines = {
        "yes": [
            "Looks good.",
            "Yes, probably.",
            "I would back it.",
            "That is a yes.",
            "Good chance."
        ],
        "maybe": [
            "Maybe.",
            "Could go either way.",
            "Too early to call.",
            "Not clear yet.",
            "Ask again later."
        ],
        "no": [
            "I would not back it.",
            "Not likely.",
            "That is a no.",
            "Probably not.",
            "Does not look great."
        ],
    }

    short_topic_tags = {
        "weather": ["Weather-wise", "Sky check", "Forecast says"],
        "money": ["Money-wise", "Cash-wise", "Wallet check"],
        "relationship": ["Love-wise", "Relationship-wise", "Heart check"],
        "work": ["Work-wise", "Job-wise", "Shift check"],
        "car": ["Car-wise", "Garage check", "Motor verdict"],
        "gaming": ["Game-wise", "Lobby check", "Queue verdict"],
        "travel": ["Travel-wise", "Trip check", "Route says"],
        "health": ["Health-wise", "Energy check", "Body says"],
        "general": ["Honestly", "Straight up", "8 ball says"],
    }

    short_followups = {
        "yes": [
            "You are fine.",
            "I would go with it.",
            "Push it a bit.",
            "That should land.",
            "I like your odds."
        ],
        "maybe": [
            "Do not force it.",
            "Give it a minute.",
            "Needs more time.",
            "Could swing fast.",
            "Wait and see."
        ],
        "no": [
            "Leave it there.",
            "Do not push it.",
            "Bad timing.",
            "I would pass.",
            "Try again later."
        ],
    }

    generic_question = question_text.strip().lower() in {"what", "what?", "huh", "eh", "idk", "i dont know", "i don't know"}
    if generic_question:
        answer = random.choice([
            "Ask a real question.",
            "That gave me nothing.",
            "Be more specific.",
            "You need to give me more than that.",
            "Even the 8 ball is confused."
        ])
    else:
        tag = random.choice(short_topic_tags.get(topic, short_topic_tags["general"]))
        main = random.choice(short_outcome_lines[outcome])
        extra = random.choice(short_followups[outcome])

        structures = [
            f"{tag}, {main}",
            f"{main} {extra}",
            f"{tag}, {main} {extra}",
            f"For {focus}, {main}",
            f"For {focus}, {main} {extra}"
        ]
        answer = random.choice(structures)

    if not is_sensitive_eightball_question(question_text) and random.random() < EIGHTBALL_CHEEKY_CHANCE:
        cheeky_short = {
            "yes": [
                "Try not to ruin it.",
                "Do not get cocky.",
                "You might be onto something."
            ],
            "maybe": [
                "Bit of a weird one though.",
                "The universe is stalling.",
                "Could be chaos either way."
            ],
            "no": [
                "That one is not it.",
                "The vibe is off.",
                "Even I would leave that."
            ],
        }
        answer = f"{answer} {random.choice(cheeky_short[outcome])}"

    return re.sub(r"\s+", " ", answer).strip(), topic, outcome


@bot.command(name="eightball", aliases=["8ball"])
async def eightball(ctx, *, question: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("8 Ball", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not question:
        embed = game_embed("8 Ball", "❌ Usage: `!8ball will I win?`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    answer, topic, outcome = build_eightball_answer(question)
    embed = discord.Embed(
        title="🎱 Magic 8 Ball",
        description=f"**Question:** {question}\n\n**Answer:** {answer}",
        colour=0x5865F2,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs Games", icon_url=LOGO_URL)
    await ctx.send(embed=embed)


@bot.command(name="choose")
async def choose(ctx, *, options: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Choose", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not options or "|" not in options:
        embed = game_embed("Choose", "❌ Usage: `!choose option 1 | option 2 | option 3`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    choices = [option.strip() for option in options.split("|") if option.strip()]
    if len(choices) < 2:
        embed = game_embed("Choose", "❌ Give me at least **2** options.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    picked = random.choice(choices)
    extras = [
        "That is the one I am backing.",
        "I would go with this option.",
        "This feels like the smartest pick.",
        "That is the one standing out most.",
        "I would not overthink it. Pick this."
    ]
    embed = game_embed("🤔 Choice Picker", f"{ctx.author.mention}, I choose: **{picked}**\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)


@bot.command(name="rps")
async def rps(ctx, choice: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Rock Paper Scissors", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not choice:
        embed = game_embed("Rock Paper Scissors", "❌ Usage: `!rps rock`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    choice = choice.lower().strip()
    valid = {"rock", "paper", "scissors"}
    if choice not in valid:
        embed = game_embed("Rock Paper Scissors", "❌ Choose `rock`, `paper`, or `scissors`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    bot_choice = random.choice(list(valid))

    if choice == bot_choice:
        result = "It's a **draw**!"
        extra = random.choice([
            "Dead even. Nobody takes it.",
            "A draw. Same move.",
            "Stalemate. Try again."
        ])
    elif (
        (choice == "rock" and bot_choice == "scissors")
        or (choice == "paper" and bot_choice == "rock")
        or (choice == "scissors" and bot_choice == "paper")
    ):
        result = "You **win**!"
        extra = random.choice([
            "You read that perfectly and took the win.",
            "That was clean. Easy win for you.",
            "You outplayed me there."
        ])
    else:
        result = "You **lose**!"
        extra = random.choice([
            "I had the better move that time.",
            "You got countered there.",
            "Not your round. I take that one."
        ])

    embed = game_embed(
        "✂️ Rock Paper Scissors",
        f"**You:** {choice.title()}\n**Me:** {bot_choice.title()}\n\n{result}\n{extra}"
    )
    await ctx.send(embed=embed)


@bot.command(name="guess")
async def guess(ctx, number: int = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Guess The Number", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if number is None:
        embed = game_embed("Guess The Number", "❌ Usage: `!guess 7`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if number < 1 or number > 10:
        embed = game_embed("Guess The Number", "❌ Pick a number between **1** and **10**.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    secret = random.randint(1, 10)
    if number == secret:
        desc = f"🎉 You guessed it! The number was **{secret}**.\n\n{random.choice(['Perfect guess. You nailed it.', 'Spot on. That was the number.', 'Straight in. You got it.'])}"
        colour = 0x2ECC71
    else:
        desc = f"❌ Not this time. You guessed **{number}**, the number was **{secret}**.\n\n{random.choice(['Close call, but not this time.', 'Wrong number this round.', 'Unlucky. The number slipped past you.'])}"
        colour = 0xE67E22

    embed = game_embed("🔢 Guess The Number", desc, colour)
    await ctx.send(embed=embed)


@bot.command(name="number")
async def number(ctx, minimum: int = None, maximum: int = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Random Number", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if minimum is None or maximum is None:
        embed = game_embed("Random Number", "❌ Usage: `!number 1 100`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if minimum >= maximum:
        embed = game_embed("Random Number", "❌ The first number must be lower than the second.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if maximum - minimum > 1000000:
        embed = game_embed("Random Number", "❌ That range is too large.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    extras = [
        "There you go.",
        "That is your number.",
        "Randomness has decided.",
        "That is the one it picked."
    ]
    embed = game_embed("🔢 Random Number", f"Your random number is **{random.randint(minimum, maximum)}**.\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)



@bot.command(name="slots")
async def slots(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Slots"))
        return

    if not await check_betting_cooldown(ctx, "slots", "Slots"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Slots", "❌ You already have an active game running.", 0xE74C3C))
        return

    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !slots",
            description=(
                "**Description:** Spin the slot machine for a cash payout\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!slots [bet]\n"
                "**Example:**\n"
                "!slots 1m"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount

    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None

    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Slots", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return

    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Slots", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return

    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Slots", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "slots")

    try:
        reels = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
        weights = [19, 17, 15, 15, 15, 19]
        spin = random.choices(reels, weights=weights, k=3)

        payout_mult = 0.0
        result_line = "No win this time."

        if spin == ["7️⃣", "7️⃣", "7️⃣"]:
            payout_mult = 12.0
            result_line = "🎉 **MEGA HIT** — triple sevens!"
        elif len(set(spin)) == 1:
            payout_mult = 7.0
            result_line = "🎉 **JACKPOT** — all 3 matched!"
        elif len(set(spin)) == 2:
            payout_mult = 2.6
            result_line = "✨ Nice hit — you landed a pair."
        elif "💎" in spin:
            payout_mult = 1.5
            result_line = "💎 Diamond saver — small return."

        payout = int(round(bet_amount * payout_mult))
        new_balance = add_user_balance(ctx.author.id, payout)
        record_house_profit("slots", bet_amount, payout, ctx.author.id)
        await check_casino_car_pack_role(ctx.author, ctx)

        message = await send_game_premessage(
            ctx,
            f"Slots - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            "🎰 Booting slot machine...",
            "⚙️ Aligning reels..."
        )

        spin_embed = discord.Embed(
            title=f"Slots - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description="🎰 | 🎰 | 🎰\n\n**Spinning...**",
            colour=0x5865F2,
            timestamp=now_dt()
        )
        spin_embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        spin_embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

        frames = 9
        for i in range(frames):
            current = random.choices(reels, weights=weights, k=3)
            if i >= frames - 3:
                current = [spin[0], current[1], current[2]] if i == frames - 3 else [spin[0], spin[1], current[2]] if i == frames - 2 else spin
            glow = "✨" * (1 + (i % 3))
            spin_embed.description = f"{' | '.join(current)}\n\n**Spinning{'.' * ((i % 3) + 1)}** {glow}"
            await message.edit(embed=spin_embed)
            await asyncio.sleep(0.18 if i < 5 else 0.24)

        result_embed = discord.Embed(
            title=f"Slots - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=(
                f"{' | '.join(spin)}\n\n"
                f"{result_line}\n"
                f"└ Won: **{format_casino_result_display(payout, new_balance, display_bet_amount)} 💵**\n"
                f"└ Balance: **{format_cash(new_balance)} 💵**"
            ),
            colour=0x57F287 if payout_mult >= 1 else 0xE67E22,
            timestamp=now_dt()
        )
        result_embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        result_embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await message.edit(embed=result_embed)
    finally:
        await asyncio.sleep(1.5)
        ACTIVE_GAME_USERS.discard(ctx.author.id)


@bot.command(name="roulette")
async def roulette(ctx, bet_amount=None, choice=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Roulette"))
        return

    if not await check_betting_cooldown(ctx, "roulette", "Roulette"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Roulette", "❌ You already have an active game running.", 0xE74C3C))
        return

    if bet_amount is None or choice is None:
        embed = discord.Embed(
            title="Command: !roulette",
            description=(
                "**Description:** Bet on roulette colours or a number\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!roulette [bet] [red/black/green/0-36]\n"
                "**Examples:**\n"
                "!roulette 500k red\n"
                "!roulette 1m 17"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount

    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None

    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Roulette", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return

    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Roulette", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return

    choice_text = str(choice).lower().strip()
    valid_colour_choices = {"red", "black", "green"}
    chosen_number = None
    if choice_text not in valid_colour_choices:
        try:
            chosen_number = int(choice_text)
        except Exception:
            chosen_number = None
        if chosen_number is None or chosen_number < 0 or chosen_number > 36:
            await ctx.send(embed=build_case_embed("Roulette", "❌ Pick `red`, `black`, `green`, or a number from `0` to `36`.", 0xE74C3C))
            return

    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Roulette", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "roulette")

    try:
        pre = await send_game_premessage(
            ctx,
            f"Roulette - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            "🎡 Spinning the wheel...",
            "🔴⚫ Ball is bouncing..."
        )
        rolled_number = random.randint(0, 36)
        red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        result_colour = "green" if rolled_number == 0 else ("red" if rolled_number in red_numbers else "black")

        payout_mult = 0.0
        won = False
        if chosen_number is not None:
            if rolled_number == chosen_number:
                won = True
                payout_mult = 20.0
        else:
            if choice_text == result_colour:
                won = True
                payout_mult = 2.62 if choice_text in {"red", "black"} else 19.0

        spin_sequence = []
        wheel_pool = list(range(37))
        random.shuffle(wheel_pool)
        spin_sequence.extend(wheel_pool[:12])
        spin_sequence.append(rolled_number)

        for idx, shown in enumerate(spin_sequence):
            shown_colour = "green" if shown == 0 else ("red" if shown in red_numbers else "black")
            window = spin_sequence[max(0, idx - 4):idx + 1]
            spin_embed = discord.Embed(
                title=f"Roulette - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
                description=(
                    "🎡 Wheel spinning...\n\n"
                    + " | ".join([f"**{n}**" if n == shown else str(n) for n in window])
                    + f"\n\nBall passing: **{shown} ({shown_colour})**"
                ),
                colour=0x5865F2,
                timestamp=now_dt()
            )
            spin_embed.set_author(name="GL Customs", icon_url=LOGO_URL)
            spin_embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
            await pre.edit(embed=spin_embed)
            await asyncio.sleep(0.08 + (idx * 0.015))

        payout = int(round(bet_amount * payout_mult))
        new_balance = add_user_balance(ctx.author.id, payout)
        record_house_profit("baccarat", bet_amount, payout, ctx.author.id)
        await check_casino_car_pack_role(ctx.author, ctx)

        embed = discord.Embed(
            title=f"Roulette - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=(
                f"🎡 Ball landed on **{rolled_number} ({result_colour})**\n"
                f"Your choice: **{choice_text}**\n\n"
                f"{'✅ You won!' if won else '❌ You lost this spin.'}\n"
                f"└ Won: **{format_casino_result_display(payout, new_balance, display_bet_amount)} 💵**\n"
                f"└ Balance: **{format_cash(new_balance)} 💵**"
            ),
            colour=0x57F287 if won else 0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await pre.edit(embed=embed)
    finally:
        ACTIVE_GAME_USERS.discard(ctx.author.id)


class CrashGameView(discord.ui.View):
    def __init__(self, author, bet_amount, ctx, display_bet_amount=None):
        super().__init__(timeout=25)
        self.author = author
        self.bet_amount = bet_amount
        self.ctx = ctx
        self.display_bet_amount = display_bet_amount
        self.message = None
        self.finished = False
        self.cashed_out = False
        self.current_multiplier = 1.00
        self.crash_point = generate_crash_point()
        self.history = [1.00]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This is not your crash game.", ephemeral=True)
            return False
        return True

    def build_bar(self):
        bar_length = 24
        progress = min(self.current_multiplier / max(self.crash_point, 1.1), 1.0)
        marker = min(bar_length - 1, max(0, int(progress * (bar_length - 1))))
        pieces = ["─"] * bar_length
        pieces[marker] = "🔴"
        return "".join(pieces)

    def build_graph(self):
        blocks = "▁▂▃▄▅▆▇█"
        recent = self.history[-12:]
        if not recent:
            return "▁"
        max_val = max(max(recent), 1.0)
        graph_parts = []
        for value in recent:
            ratio = min(value / max_val, 1.0)
            index = min(len(blocks) - 1, max(0, int(round(ratio * (len(blocks) - 1)))))
            graph_parts.append(blocks[index])
        return "".join(graph_parts)

    def build_embed(self, final_text=None, colour=0x5865F2):
        graph = self.build_graph()
        desc = (
            f"📈 Current multiplier: **{self.current_multiplier:.2f}x**\n"
            f"```{graph}```\n"
            f"`{self.build_bar()}`\n\n"
            f"{final_text if final_text else 'Hit **Cash Out** before it crashes.'}"
        )
        embed = discord.Embed(
            title=f"Crash - {format_casino_bet_display(display_bet_amount=self.display_bet_amount)} 💵",
            description=desc,
            colour=colour,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        return embed

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success)
    async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.defer()
            return
        self.finished = True
        self.cashed_out = True
        payout = int(round(self.bet_amount * self.current_multiplier))
        new_balance = add_user_balance(self.author.id, payout)
        record_house_profit("crash", self.bet_amount, payout, self.author.id)
        await check_casino_car_pack_role(self.author, self.ctx)
        ACTIVE_GAME_USERS.discard(self.author.id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=self.build_embed(
                final_text=f"✅ You cashed out at **{self.current_multiplier:.2f}x**\n└ Won: **{format_casino_result_display(payout, new_balance, self.display_bet_amount)} 💵**\n└ Balance: **{format_cash(new_balance)} 💵**",
                colour=0x57F287
            ),
            view=self
        )

    async def run(self):
        while not self.finished:
            await asyncio.sleep(0.22 if self.current_multiplier < 2 else 0.16 if self.current_multiplier < 5 else 0.12)
            growth = 1.06 if self.current_multiplier < 2 else 1.09 if self.current_multiplier < 5 else 1.12
            self.current_multiplier = round(self.current_multiplier * growth, 2)
            self.history.append(self.current_multiplier)
            if self.current_multiplier >= self.crash_point:
                self.current_multiplier = self.crash_point
                self.history[-1] = self.crash_point
                self.finished = True
                record_house_profit("crash", self.bet_amount, 0, self.author.id)
                ACTIVE_GAME_USERS.discard(self.author.id)
                for child in self.children:
                    child.disabled = True
                if self.message:
                    await self.message.edit(
                        embed=self.build_embed(
                            final_text=f"💥 CRASHED at **{self.crash_point:.2f}x**\n└ Won: **{format_casino_result_display(0, get_user_balance(self.author.id), self.display_bet_amount)} 💵**\n└ Balance: **{format_cash(get_user_balance(self.author.id))} 💵**",
                            colour=0xE74C3C
                        ),
                        view=self
                    )
                return
            if self.message:
                await self.message.edit(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        if not self.finished:
            self.finished = True
            ACTIVE_GAME_USERS.discard(self.author.id)
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(
                    embed=self.build_embed(
                        final_text=f"⏱️ Timed out before cashing out.\n└ Won: **{format_casino_result_display(0, get_user_balance(self.author.id), self.display_bet_amount)} 💵**\n└ Balance: **{format_cash(get_user_balance(self.author.id))} 💵**",
                        colour=0xE67E22
                    ),
                    view=self
                )


@bot.command(name="crash")
async def crash(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Crash"))
        return
    if not await check_betting_cooldown(ctx, "crash", "Crash"):
        return
    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Crash", "❌ You already have an active game running.", 0xE74C3C))
        return
    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !crash",
            description=(
                "**Description:** Cash out before the multiplier crashes\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!crash [bet/all]\n"
                "**Examples:**\n"
                "!crash 500k\n"
                "!crash all"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return
    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None
    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Crash", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return
    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Crash", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return
    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Crash", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return
    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "crash")
    view = CrashGameView(ctx.author, bet_amount, ctx, display_bet_amount=display_bet_amount)
    message = await send_game_premessage(
        ctx,
        f"Crash - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
        "🚀 Starting crash engine...",
        "📡 Building launch graph..."
    )
    for countdown in [2, 1]:
        embed = discord.Embed(
            title=f"Crash - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=f"🚀 Launching in **{countdown}**...\n\nGet ready to cash out.",
            colour=0x5865F2,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
    await message.edit(embed=view.build_embed(), view=view)
    view.message = message
    await view.run()


@bot.command(name="dice")
async def dice(ctx, bet_amount=None, side=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Dice"))
        return
    if not await check_betting_cooldown(ctx, "dice", "Dice"):
        return
    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Dice", "❌ You already have an active game running.", 0xE74C3C))
        return
    if bet_amount is None or side is None:
        embed = discord.Embed(
            title="Command: !dice",
            description=(
                "**Description:** Bet on high or low with a fast dice roll\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!dice [bet/all] [high/low]\n"
                "**Example:**\n"
                "!dice all high"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return
    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None
    side = str(side).lower().strip()
    if side not in {"high", "low"}:
        await ctx.send(embed=build_case_embed("Dice", "❌ Pick either `high` or `low`.", 0xE74C3C))
        return
    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Dice", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return
    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Dice", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return
    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Dice", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return
    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "dice")
    try:
        final_roll = random.randint(1, 100)
        won = (side == "low" and final_roll <= 49) or (side == "high" and final_roll >= 52)
        payout = int(round(bet_amount * 2.15)) if won else 0
        new_balance = add_user_balance(ctx.author.id, payout)
        record_house_profit("dice", bet_amount, payout, ctx.author.id)
        await check_casino_car_pack_role(ctx.author, ctx)
        embed = discord.Embed(
            title=f"Dice - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=f"Your call: **{side}**\n\n🎲 Rolling...",
            colour=0x5865F2,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        message = await ctx.send(embed=embed)
        preview_rolls = [random.randint(1, 100) for _ in range(6)] + [final_roll]
        for idx, shown_roll in enumerate(preview_rolls):
            pulse = "🟥" if shown_roll >= 52 else "🟦" if shown_roll <= 49 else "🟨"
            embed.description = f"Your call: **{side}**\n\n🎲 Rolling... {pulse} **{shown_roll}**"
            await message.edit(embed=embed)
            await asyncio.sleep(0.16 if idx < 4 else 0.22)
        embed.description = (
            f"🎲 Roll: **{final_roll}**\n"
            f"Your call: **{side}**\n\n"
            f"{'✅ You won the roll!' if won else '❌ You lost the roll.'}\n"
            f"└ Won: **{format_casino_result_display(payout, new_balance, display_bet_amount)} 💵**\n"
            f"└ Balance: **{format_cash(new_balance)} 💵**"
        )
        embed.colour = 0x57F287 if won else 0xE74C3C
        await message.edit(embed=embed)
    finally:
        ACTIVE_GAME_USERS.discard(ctx.author.id)


@bot.command(name="baccarat")

async def baccarat(ctx, bet_amount=None, side=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Baccarat"))
        return

    if not await check_betting_cooldown(ctx, "baccarat", "Baccarat"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Baccarat", "❌ You already have an active game running.", 0xE74C3C))
        return

    if bet_amount is None or side is None:
        embed = discord.Embed(
            title="Command: !baccarat",
            description=(
                "**Description:** Back player, banker, or tie\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!baccarat [bet] [player/banker/tie]\n"
                "**Example:**\n"
                "!baccarat 1m banker"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    side = str(side).lower().strip()
    if side not in {"player", "banker", "tie"}:
        await ctx.send(embed=build_case_embed("Baccarat", "❌ Pick `player`, `banker`, or `tie`.", 0xE74C3C))
        return

    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Baccarat", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return

    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Baccarat", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return

    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Baccarat", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "baccarat")

    try:
        outcome = random.choices(["player", "banker", "tie"], weights=[446, 458, 96], k=1)[0]
        won = side == outcome
        payout_mult = {"player": 2.25, "banker": 2.18, "tie": 10.2}[outcome] if won else 0.0
        payout = int(round(bet_amount * payout_mult))
        new_balance = add_user_balance(ctx.author.id, payout)
        record_house_profit("roulette", bet_amount, payout, ctx.author.id)
        await check_casino_car_pack_role(ctx.author, ctx)

        embed = discord.Embed(
            title=f"Baccarat - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=(
                f"🃏 Outcome: **{outcome.title()}**\n"
                f"Your side: **{side.title()}**\n\n"
                f"{'✅ You won the hand!' if won else '❌ You lost the hand.'}\n"
                f"└ Won: **{format_casino_result_display(payout, new_balance, display_bet_amount)} 💵**\n"
                f"└ Balance: **{format_cash(new_balance)} 💵**"
            ),
            colour=0x57F287 if won else 0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
    finally:
        ACTIVE_GAME_USERS.discard(ctx.author.id)





CHESS_UNICODE_PIECES = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": "·"
}

CHESS_PIECE_VALUES = {
    "p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 0
}


def chess_in_bounds(row, col):
    return 0 <= row < 8 and 0 <= col < 8


class CasinoChessGame:
    def __init__(self, user_id, bet_amount, display_bet_amount):
        self.user_id = int(user_id)
        self.bet_amount = int(bet_amount)
        self.display_bet_amount = display_bet_amount
        self.board = [
            list("rnbqkbnr"),
            list("pppppppp"),
            list("........"),
            list("........"),
            list("........"),
            list("........"),
            list("PPPPPPPP"),
            list("RNBQKBNR"),
        ]
        self.castling = {"K": True, "Q": True, "k": True, "q": True}
        self.status = "Choose a piece, then choose where it moves."
        self.last_move = "None yet"
        self.last_move_squares = []
        self.white_captures = []
        self.black_captures = []
        self.move_history = []
        self.finished = False
        self.result = None
        self.result_line = None
        self.payout = 0
        self.final_balance = None

    @staticmethod
    def side_name(turn):
        return "White" if turn == "w" else "Black"

    def render_board(self):
        lines = []
        for row in range(8):
            rank = 8 - row
            pieces = " ".join(CHESS_UNICODE_PIECES.get(piece, piece) for piece in self.board[row])
            lines.append(f"{rank} {pieces}")
        lines.append("  a b c d e f g h")
        return "```\n" + "\n".join(lines) + "\n```"


def chess_piece_badge(piece):
    if piece == ".":
        return ""
    return f"{'W' if piece.isupper() else 'B'}{piece.upper()}"


def chess_format_captured_pieces(pieces):
    if not pieces:
        return "None"
    return " ".join(chess_piece_badge(piece) for piece in pieces)


def chess_format_move_history(move_history, max_pairs=6):
    if not move_history:
        return "None yet"

    pair_count = (len(move_history) + 1) // 2
    start_pair = max(0, pair_count - max_pairs)
    lines = []

    for pair_index in range(start_pair, pair_count):
        white_index = pair_index * 2
        black_index = white_index + 1
        white_move = move_history[white_index] if white_index < len(move_history) else "..."
        black_move = move_history[black_index] if black_index < len(move_history) else "..."
        lines.append(f"{pair_index + 1}. {white_move} | {black_move}")

    return "\n".join(lines)


def chess_status_badge_info(status_label):
    text = str(status_label or "").upper()
    if "CHECKMATE" in text:
        return "CHECKMATE", (87, 242, 135), (22, 24, 30)
    if "CHECK" in text:
        return "CHECK", (241, 196, 15), (22, 24, 30)
    if "STALEMATE" in text or "DRAW" in text:
        return "DRAW", (88, 101, 242), (245, 247, 250)
    if "RESIGNED" in text or "LOST" in text or "TIME OUT" in text or "TIMED OUT" in text:
        return "LOSS", (237, 66, 69), (245, 247, 250)
    if "WON" in text:
        return "WIN", (87, 242, 135), (22, 24, 30)
    if "THINKING" in text:
        return "BOT", (88, 101, 242), (245, 247, 250)
    return "YOUR TURN", (88, 101, 242), (245, 247, 250)


def chess_piece_color(piece):
    if piece == ".":
        return None
    return "w" if piece.isupper() else "b"


def chess_opponent(turn):
    return "b" if turn == "w" else "w"


def chess_square_to_coords(square):
    square = str(square).strip().lower()
    if len(square) != 2 or square[0] not in "abcdefgh" or square[1] not in "12345678":
        return None
    col = ord(square[0]) - ord("a")
    row = 8 - int(square[1])
    return row, col


def chess_coords_to_square(row, col):
    return f"{chr(ord('a') + col)}{8 - row}"


def chess_find_king(board, turn):
    target = "K" if turn == "w" else "k"
    for row in range(8):
        for col in range(8):
            if board[row][col] == target:
                return row, col
    return None


def chess_is_square_attacked(board, row, col, by_turn):
    pawn = "P" if by_turn == "w" else "p"
    pawn_dirs = [(-1, -1), (-1, 1)] if by_turn == "b" else [(1, -1), (1, 1)]
    for dr, dc in pawn_dirs:
        rr, cc = row + dr, col + dc
        if chess_in_bounds(rr, cc) and board[rr][cc] == pawn:
            return True

    knight = "N" if by_turn == "w" else "n"
    for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
        rr, cc = row + dr, col + dc
        if chess_in_bounds(rr, cc) and board[rr][cc] == knight:
            return True

    bishop = "B" if by_turn == "w" else "b"
    rook = "R" if by_turn == "w" else "r"
    queen = "Q" if by_turn == "w" else "q"
    king = "K" if by_turn == "w" else "k"

    for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        rr, cc = row + dr, col + dc
        while chess_in_bounds(rr, cc):
            piece = board[rr][cc]
            if piece != ".":
                if piece in {bishop, queen}:
                    return True
                break
            rr += dr
            cc += dc

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        rr, cc = row + dr, col + dc
        while chess_in_bounds(rr, cc):
            piece = board[rr][cc]
            if piece != ".":
                if piece in {rook, queen}:
                    return True
                break
            rr += dr
            cc += dc

    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = row + dr, col + dc
            if chess_in_bounds(rr, cc) and board[rr][cc] == king:
                return True

    return False


def chess_in_check(board, turn):
    king_pos = chess_find_king(board, turn)
    if king_pos is None:
        return True
    return chess_is_square_attacked(board, king_pos[0], king_pos[1], chess_opponent(turn))


def chess_clone_board(board):
    return [row[:] for row in board]


def chess_apply_move(board, move, castling):
    new_board = chess_clone_board(board)
    new_castling = dict(castling)

    fr, fc = move["from"]
    tr, tc = move["to"]
    piece = new_board[fr][fc]
    captured = new_board[tr][tc]

    if piece == "K":
        new_castling["K"] = False
        new_castling["Q"] = False
    elif piece == "k":
        new_castling["k"] = False
        new_castling["q"] = False
    elif piece == "R":
        if (fr, fc) == (7, 0):
            new_castling["Q"] = False
        elif (fr, fc) == (7, 7):
            new_castling["K"] = False
    elif piece == "r":
        if (fr, fc) == (0, 0):
            new_castling["q"] = False
        elif (fr, fc) == (0, 7):
            new_castling["k"] = False

    if captured == "R":
        if (tr, tc) == (7, 0):
            new_castling["Q"] = False
        elif (tr, tc) == (7, 7):
            new_castling["K"] = False
    elif captured == "r":
        if (tr, tc) == (0, 0):
            new_castling["q"] = False
        elif (tr, tc) == (0, 7):
            new_castling["k"] = False

    new_board[fr][fc] = "."
    new_board[tr][tc] = piece

    if move.get("promotion"):
        new_board[tr][tc] = move["promotion"]

    castle_side = move.get("castle")
    if castle_side == "K":
        new_board[7][7] = "."
        new_board[7][5] = "R"
    elif castle_side == "Q":
        new_board[7][0] = "."
        new_board[7][3] = "R"
    elif castle_side == "k":
        new_board[0][7] = "."
        new_board[0][5] = "r"
    elif castle_side == "q":
        new_board[0][0] = "."
        new_board[0][3] = "r"

    return new_board, new_castling


def chess_generate_pseudo_moves(board, turn, castling):
    moves = []
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == "." or chess_piece_color(piece) != turn:
                continue

            lower = piece.lower()
            if lower == "p":
                direction = -1 if turn == "w" else 1
                start_row = 6 if turn == "w" else 1
                promotion_row = 0 if turn == "w" else 7
                next_row = row + direction
                if chess_in_bounds(next_row, col) and board[next_row][col] == ".":
                    if next_row == promotion_row:
                        for promo in ["Q", "R", "B", "N"] if turn == "w" else ["q", "r", "b", "n"]:
                            moves.append({"from": (row, col), "to": (next_row, col), "promotion": promo})
                    else:
                        moves.append({"from": (row, col), "to": (next_row, col), "promotion": None})
                        jump_row = row + (2 * direction)
                        if row == start_row and board[jump_row][col] == ".":
                            moves.append({"from": (row, col), "to": (jump_row, col), "promotion": None})
                for dc in (-1, 1):
                    capture_col = col + dc
                    if not chess_in_bounds(next_row, capture_col):
                        continue
                    target = board[next_row][capture_col]
                    if target != "." and chess_piece_color(target) == chess_opponent(turn):
                        if next_row == promotion_row:
                            for promo in ["Q", "R", "B", "N"] if turn == "w" else ["q", "r", "b", "n"]:
                                moves.append({"from": (row, col), "to": (next_row, capture_col), "promotion": promo})
                        else:
                            moves.append({"from": (row, col), "to": (next_row, capture_col), "promotion": None})

            elif lower == "n":
                for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
                    rr, cc = row + dr, col + dc
                    if not chess_in_bounds(rr, cc):
                        continue
                    target = board[rr][cc]
                    if target == "." or chess_piece_color(target) == chess_opponent(turn):
                        moves.append({"from": (row, col), "to": (rr, cc), "promotion": None})

            elif lower in {"b", "r", "q"}:
                directions = []
                if lower in {"b", "q"}:
                    directions.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
                if lower in {"r", "q"}:
                    directions.extend([(-1, 0), (1, 0), (0, -1), (0, 1)])
                for dr, dc in directions:
                    rr, cc = row + dr, col + dc
                    while chess_in_bounds(rr, cc):
                        target = board[rr][cc]
                        if target == ".":
                            moves.append({"from": (row, col), "to": (rr, cc), "promotion": None})
                        else:
                            if chess_piece_color(target) == chess_opponent(turn):
                                moves.append({"from": (row, col), "to": (rr, cc), "promotion": None})
                            break
                        rr += dr
                        cc += dc

            elif lower == "k":
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = row + dr, col + dc
                        if not chess_in_bounds(rr, cc):
                            continue
                        target = board[rr][cc]
                        if target == "." or chess_piece_color(target) == chess_opponent(turn):
                            moves.append({"from": (row, col), "to": (rr, cc), "promotion": None})

                if turn == "w" and row == 7 and col == 4 and piece == "K":
                    if castling.get("K") and board[7][5] == "." and board[7][6] == ".":
                        if not chess_in_check(board, "w") and not chess_is_square_attacked(board, 7, 5, "b") and not chess_is_square_attacked(board, 7, 6, "b"):
                            if board[7][7] == "R":
                                moves.append({"from": (7, 4), "to": (7, 6), "promotion": None, "castle": "K"})
                    if castling.get("Q") and board[7][1] == "." and board[7][2] == "." and board[7][3] == ".":
                        if not chess_in_check(board, "w") and not chess_is_square_attacked(board, 7, 3, "b") and not chess_is_square_attacked(board, 7, 2, "b"):
                            if board[7][0] == "R":
                                moves.append({"from": (7, 4), "to": (7, 2), "promotion": None, "castle": "Q"})
                elif turn == "b" and row == 0 and col == 4 and piece == "k":
                    if castling.get("k") and board[0][5] == "." and board[0][6] == ".":
                        if not chess_in_check(board, "b") and not chess_is_square_attacked(board, 0, 5, "w") and not chess_is_square_attacked(board, 0, 6, "w"):
                            if board[0][7] == "r":
                                moves.append({"from": (0, 4), "to": (0, 6), "promotion": None, "castle": "k"})
                    if castling.get("q") and board[0][1] == "." and board[0][2] == "." and board[0][3] == ".":
                        if not chess_in_check(board, "b") and not chess_is_square_attacked(board, 0, 3, "w") and not chess_is_square_attacked(board, 0, 2, "w"):
                            if board[0][0] == "r":
                                moves.append({"from": (0, 4), "to": (0, 2), "promotion": None, "castle": "q"})
    return moves


def chess_generate_legal_moves(board, turn, castling):
    legal = []
    for move in chess_generate_pseudo_moves(board, turn, castling):
        new_board, new_castling = chess_apply_move(board, move, castling)
        if not chess_in_check(new_board, turn):
            checked_move = dict(move)
            checked_move["castling_after"] = new_castling
            legal.append(checked_move)
    return legal


def chess_move_to_text(move):
    text = chess_coords_to_square(*move["from"]) + chess_coords_to_square(*move["to"])
    if move.get("promotion"):
        text += move["promotion"].lower()
    return text


def chess_match_user_move(raw_move, legal_moves):
    cleaned = str(raw_move).strip().lower().replace(" ", "")
    if len(cleaned) not in {4, 5}:
        return None
    from_sq = chess_square_to_coords(cleaned[:2])
    to_sq = chess_square_to_coords(cleaned[2:4])
    if from_sq is None or to_sq is None:
        return None
    promotion = cleaned[4] if len(cleaned) == 5 else None

    for move in legal_moves:
        if move["from"] != from_sq or move["to"] != to_sq:
            continue
        move_promo = move.get("promotion")
        if move_promo is None:
            if promotion is None:
                return move
            continue
        if promotion is None:
            if move_promo.lower() == "q":
                return move
            continue
        if move_promo.lower() == promotion:
            return move
    return None


def chess_material_delta_for_black(board):
    score = 0
    for row in board:
        for piece in row:
            if piece == ".":
                continue
            value = CHESS_PIECE_VALUES.get(piece.lower(), 0)
            if piece.islower():
                score += value
            else:
                score -= value
    return score


def chess_choose_bot_move(game):
    legal_moves = chess_generate_legal_moves(game.board, "b", game.castling)
    if not legal_moves:
        return None

    ranked = []
    for move in legal_moves:
        target_piece = game.board[move["to"][0]][move["to"][1]]
        new_board, new_castling = chess_apply_move(game.board, move, game.castling)
        white_moves = chess_generate_legal_moves(new_board, "w", new_castling)
        score = 0.0
        if target_piece != ".":
            score += CHESS_PIECE_VALUES.get(target_piece.lower(), 0) * 12
        if move.get("promotion"):
            score += 8
        if chess_in_check(new_board, "w"):
            score += 4
        if not white_moves:
            if chess_in_check(new_board, "w"):
                score += 1000
            else:
                score += 20
        score += chess_material_delta_for_black(new_board) * 0.6
        score += __import__("random").random()
        ranked.append((score, move))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


CHESS_BOARD_FILENAME = "chess_board.png"
CHESS_BOARD_MARGIN = 34
CHESS_SQUARE_SIZE = 72
CHESS_FONT_CACHE = {}


def chess_blend(base, overlay, alpha):
    return tuple(int(base[i] * (1 - alpha) + overlay[i] * alpha) for i in range(3))


def chess_load_font(size):
    if not PIL_AVAILABLE:
        return None

    key = int(size)
    if key in CHESS_FONT_CACHE:
        return CHESS_FONT_CACHE[key]

    candidate_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]
    for font_path in candidate_paths:
        try:
            font = ImageFont.truetype(font_path, key)
            CHESS_FONT_CACHE[key] = font
            return font
        except Exception:
            pass

    font = ImageFont.load_default()
    CHESS_FONT_CACHE[key] = font
    return font

def chess_render_board_image(board, selected_from=None, legal_moves=None, last_move_squares=None, check_square=None, white_captures=None, black_captures=None, status_label=None):
    if not PIL_AVAILABLE:
        return None

    light_sq = (236, 219, 186)
    dark_sq = (181, 136, 99)
    bg_top = (17, 20, 29)
    bg_bottom = (24, 28, 39)
    panel_bg = (31, 36, 49)
    panel_border = (70, 76, 91)
    coord_color = (220, 223, 228)
    board_border = (70, 76, 91)

    white_fill = (245, 247, 250)
    white_outline = (78, 84, 92)
    white_text = (36, 38, 44)

    black_fill = (54, 57, 66)
    black_outline = (235, 238, 242)
    black_text = (245, 247, 250)

    size = CHESS_SQUARE_SIZE
    margin = CHESS_BOARD_MARGIN
    board_px = size * 8
    header_h = 34
    footer_gap = 28
    side_w = 236

    canvas_w = board_px + margin * 2 + side_w + 14
    canvas_h = board_px + margin * 2 + header_h + footer_gap

    img = Image.new("RGBA", (canvas_w, canvas_h), bg_top + (255,))
    draw = ImageDraw.Draw(img)

    for y in range(canvas_h):
        ratio = y / max(canvas_h - 1, 1)
        colour = tuple(int(bg_top[i] * (1 - ratio) + bg_bottom[i] * ratio) for i in range(3))
        draw.line((0, y, canvas_w, y), fill=colour)

    coord_font = chess_load_font(20)
    label_font = chess_load_font(18)
    small_font = chess_load_font(15)
    piece_font = chess_load_font(16)
    badge_font = chess_load_font(16)

    board_top = margin + header_h
    board_bottom = board_top + board_px
    board_left = margin
    board_right = board_left + board_px

    panel_left = board_right + 18
    panel_top = 14
    panel_right = canvas_w - 14
    panel_bottom = canvas_h - 14

    draw.rounded_rectangle(
        [10, 10, board_right + 10, canvas_h - 10],
        radius=18,
        fill=(28, 31, 40, 235),
        outline=(44, 48, 58),
        width=2
    )
    draw.rounded_rectangle(
        [panel_left, panel_top, panel_right, panel_bottom],
        radius=18,
        fill=panel_bg + (230,),
        outline=panel_border,
        width=2
    )

    draw.text((board_left, 14), "BOT • Black", font=label_font, fill=(235, 238, 242))
    bottom_label_bbox = draw.textbbox((0, 0), "YOU • White", font=label_font)
    bottom_label_w = bottom_label_bbox[2] - bottom_label_bbox[0]
    draw.text((board_right - bottom_label_w, board_bottom + 8), "YOU • White", font=label_font, fill=(235, 238, 242))

    selected_coords = chess_square_to_coords(selected_from) if selected_from else None
    legal_destinations = {tuple(move["to"]) for move in (legal_moves or [])}
    last_move_set = set(tuple(x) for x in (last_move_squares or []))

    for row in range(8):
        for col in range(8):
            x0 = board_left + col * size
            y0 = board_top + row * size
            x1 = x0 + size
            y1 = y0 + size

            fill = light_sq if (row + col) % 2 == 0 else dark_sq
            if (row, col) in last_move_set:
                fill = chess_blend(fill, (246, 201, 88), 0.55)
            if selected_coords == (row, col):
                fill = chess_blend(fill, (88, 101, 242), 0.62)
            if check_square == (row, col):
                fill = chess_blend(fill, (237, 66, 69), 0.68)

            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=(45, 48, 56))

    draw.rectangle([board_left - 2, board_top - 2, board_right + 2, board_bottom + 2], outline=board_border, width=3)

    for row in range(8):
        rank = str(8 - row)
        bbox = draw.textbbox((0, 0), rank, font=coord_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((board_left / 2 - tw / 2 + 2, board_top + row * size + size / 2 - th / 2), rank, font=coord_font, fill=coord_color)

    for col in range(8):
        file_char = chr(ord("a") + col)
        bbox = draw.textbbox((0, 0), file_char, font=coord_font)
        tw = bbox[2] - bbox[0]
        draw.text((board_left + col * size + size / 2 - tw / 2, board_bottom + 2), file_char, font=coord_font, fill=coord_color)

    for row, col in legal_destinations:
        x0 = board_left + col * size
        y0 = board_top + row * size
        x1 = x0 + size
        y1 = y0 + size
        target_piece = board[row][col]
        if target_piece == ".":
            r = 10
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(87, 242, 135, 220))
        else:
            draw.rounded_rectangle([x0 + 5, y0 + 5, x1 - 5, y1 - 5], radius=12, outline=(87, 242, 135), width=4)

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == ".":
                continue

            x0 = board_left + col * size
            y0 = board_top + row * size
            x1 = x0 + size
            y1 = y0 + size
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2

            tag = chess_piece_badge(piece)
            is_white = piece.isupper()

            piece_fill = white_fill if is_white else black_fill
            piece_outline = white_outline if is_white else black_outline
            piece_text = white_text if is_white else black_text

            token_w = size * 0.64
            token_h = size * 0.34
            tx0 = cx - token_w / 2
            ty0 = cy - token_h / 2
            tx1 = cx + token_w / 2
            ty1 = cy + token_h / 2

            draw.rounded_rectangle([tx0, ty0 + 2, tx1, ty1 + 2], radius=10, fill=(0, 0, 0, 80))
            draw.rounded_rectangle([tx0, ty0, tx1, ty1], radius=10, fill=piece_fill, outline=piece_outline, width=2)

            bbox = draw.textbbox((0, 0), tag, font=piece_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw / 2, cy - th / 2 - 1), tag, font=piece_font, fill=piece_text)

    pill_text, pill_fill, pill_text_fill = chess_status_badge_info(status_label)
    pill_bbox = draw.textbbox((0, 0), pill_text, font=badge_font)
    pill_tw = pill_bbox[2] - pill_bbox[0]
    pill_th = pill_bbox[3] - pill_bbox[1]
    pill_x0 = board_left + 12
    pill_y0 = board_top + 12
    pill_x1 = pill_x0 + pill_tw + 24
    pill_y1 = pill_y0 + pill_th + 14
    draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=14, fill=pill_fill, outline=(255, 255, 255, 70), width=1)
    draw.text((pill_x0 + 12, pill_y0 + 7), pill_text, font=badge_font, fill=pill_text_fill)

    draw.text((panel_left + 16, panel_top + 16), "STATUS", font=small_font, fill=(166, 173, 191))
    draw.rounded_rectangle([panel_left + 16, panel_top + 40, panel_right - 16, panel_top + 82], radius=14, fill=(23, 26, 34), outline=(55, 61, 73), width=2)
    status_text = str(status_label or "Your turn")
    draw.text((panel_left + 28, panel_top + 54), status_text[:42], font=small_font, fill=(245, 247, 250))

    def draw_capture_section(title, pieces, top_y):
        draw.text((panel_left + 16, top_y), title, font=small_font, fill=(166, 173, 191))
        box_top = top_y + 20
        box_bottom = box_top + 120
        draw.rounded_rectangle([panel_left + 16, box_top, panel_right - 16, box_bottom], radius=14, fill=(23, 26, 34), outline=(55, 61, 73), width=2)

        pieces = pieces or []
        if not pieces:
            draw.text((panel_left + 28, box_top + 44), "None", font=label_font, fill=(200, 205, 214))
            return

        start_x = panel_left + 28
        start_y = box_top + 16
        col_gap = 82
        row_gap = 38
        for idx, piece in enumerate(pieces[:12]):
            row = idx // 2
            col = idx % 2
            bx = start_x + col * col_gap
            by = start_y + row * row_gap

            is_white = piece.isupper()
            fill = white_fill if is_white else black_fill
            outline = white_outline if is_white else black_outline
            text_fill = white_text if is_white else black_text
            tag = chess_piece_badge(piece)

            draw.rounded_rectangle([bx, by, bx + 64, by + 26], radius=10, fill=fill, outline=outline, width=2)
            bbox = draw.textbbox((0, 0), tag, font=piece_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((bx + 32 - tw / 2, by + 13 - th / 2 - 1), tag, font=piece_font, fill=text_fill)

    draw_capture_section("CAPTURED BY YOU", white_captures or [], panel_top + 100)
    draw_capture_section("CAPTURED BY BOT", black_captures or [], panel_top + 252)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class ChessPieceSelect(discord.ui.Select):
    def __init__(self, chess_view, origin_moves):
        self.chess_view = chess_view
        options = []
        for square, moves in origin_moves:
            description = f"{len(moves)} legal move{'s' if len(moves) != 1 else ''} from {square}"
            options.append(discord.SelectOption(label=square, value=square, description=description))

        super().__init__(
            placeholder="Choose the piece you want to move...",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        square = self.values[0]
        self.chess_view.selected_from = square
        legal_moves = chess_generate_legal_moves(self.chess_view.game.board, "w", self.chess_view.game.castling)
        self.chess_view.selected_moves = [m for m in legal_moves if chess_coords_to_square(*m["from"]) == square]
        self.chess_view.game.status = f"Selected **{square}**. Now choose the destination square."
        self.chess_view.rebuild_components()
        await self.chess_view.update_message(interaction)


class ChessDestinationSelect(discord.ui.Select):
    def __init__(self, chess_view, moves):
        self.chess_view = chess_view
        options = []
        for move in moves:
            raw = chess_move_to_text(move)
            to_square = chess_coords_to_square(*move["to"])
            target_piece = self.chess_view.game.board[move["to"][0]][move["to"][1]]
            move_type = "Move"

            if move.get("castle"):
                move_type = "Castle"
            elif target_piece != ".":
                move_type = "Capture"
            elif move.get("promotion"):
                move_type = "Promotion"

            description = f"{move_type} to {to_square}"
            if move.get("promotion"):
                description += f" • promote to {move['promotion'].upper()}"

            options.append(discord.SelectOption(label=to_square, value=raw, description=description[:100]))

        super().__init__(
            placeholder=f"Choose where {self.chess_view.selected_from} should move...",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await self.chess_view.process_move(interaction, self.values[0])


class ChessRefreshButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        view.rebuild_components()
        await view.update_message(interaction)


class ChessClearButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Clear", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        view.selected_from = None
        view.selected_moves = []
        view.game.status = "Selection cleared. Choose a piece to move."
        view.rebuild_components()
        await view.update_message(interaction)


class ChessResignButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Resign", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view.game.finished:
            await interaction.response.send_message("❌ This chess game has already finished.", ephemeral=True)
            return
        await interaction.response.defer()
        await view.finish_game("loss", f"❌ You resigned and lost **{format_casino_result_display(view.game.bet_amount, None, view.game.display_bet_amount)} 💵**.", 0)
        await view.update_message(interaction)


class CasinoChessView(discord.ui.View):
    def __init__(self, ctx, game: CasinoChessGame):
        super().__init__(timeout=900)
        self.ctx = ctx
        self.game = game
        self.message = None
        self.selected_from = None
        self.selected_moves = []
        self.rebuild_components()

    def rebuild_components(self):
        self.clear_items()

        if self.game.finished:
            return

        legal_moves = chess_generate_legal_moves(self.game.board, "w", self.game.castling)
        grouped = {}
        for move in legal_moves:
            square = chess_coords_to_square(*move["from"])
            grouped.setdefault(square, []).append(move)

        origin_moves = sorted(grouped.items(), key=lambda item: item[0])
        if origin_moves:
            self.add_item(ChessPieceSelect(self, origin_moves))

        if self.selected_from:
            self.selected_moves = grouped.get(self.selected_from, [])
            if self.selected_moves:
                self.add_item(ChessDestinationSelect(self, self.selected_moves))
            else:
                self.selected_from = None
                self.selected_moves = []

        self.add_item(ChessRefreshButton())
        if self.selected_from:
            self.add_item(ChessClearButton())
        self.add_item(ChessResignButton())

    def build_board_file(self):
        if not PIL_AVAILABLE:
            return None

        check_square = None
        if chess_in_check(self.game.board, "w"):
            check_square = chess_find_king(self.game.board, "w")
        elif chess_in_check(self.game.board, "b"):
            check_square = chess_find_king(self.game.board, "b")

        status_line = self.game.result_line if self.game.finished and self.game.result_line else self.game.status

        img_buf = chess_render_board_image(
            self.game.board,
            selected_from=self.selected_from,
            legal_moves=self.selected_moves,
            last_move_squares=self.game.last_move_squares,
            check_square=check_square,
            white_captures=self.game.white_captures,
            black_captures=self.game.black_captures,
            status_label=status_line,
        )
        if img_buf is None:
            return None
        return discord.File(fp=img_buf, filename=CHESS_BOARD_FILENAME)

    def build_embed(self):
        colour = 0x5865F2
        if self.game.finished:
            if self.game.result == "win":
                colour = 0x57F287
            elif self.game.result == "draw":
                colour = 0xF1C40F
            else:
                colour = 0xE74C3C
        elif chess_in_check(self.game.board, "w") or chess_in_check(self.game.board, "b"):
            colour = 0xF1C40F

        balance_value = self.game.final_balance if self.game.final_balance is not None else get_user_balance(self.ctx.author.id)
        selected_line = f"**Selected piece:** {self.selected_from}\n" if self.selected_from and not self.game.finished else ""
        board_preview = f"{self.game.render_board()}\n" if not PIL_AVAILABLE else ""
        status_line = self.game.result_line if self.game.finished and self.game.result_line else self.game.status

        embed = discord.Embed(
            title=f"Chess - {format_casino_bet_display(display_bet_amount=self.game.display_bet_amount)} 💵",
            description=(
                f"{board_preview}"
                f"**You:** White\n"
                f"**Bot:** Black\n"
                f"{selected_line}"
                f"**Last move:** {self.game.last_move}\n"
                f"**Status:** {status_line}\n"
                f"**Balance:** {format_cash(balance_value)} 💵"
            ),
            colour=colour,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Chess", icon_url=LOGO_URL)

        embed.add_field(name="Moves Played", value=str(len(self.game.move_history)), inline=True)
        embed.add_field(name="You Captured", value=str(len(self.game.white_captures)), inline=True)
        embed.add_field(name="Bot Captured", value=str(len(self.game.black_captures)), inline=True)
        embed.add_field(
            name="Move History",
            value=f"```\n{chess_format_move_history(self.game.move_history)}\n```",
            inline=False
        )

        if PIL_AVAILABLE:
            embed.set_image(url=f"attachment://{CHESS_BOARD_FILENAME}")
        return embed

    async def update_message(self, interaction=None):
        embed = self.build_embed()
        board_file = self.build_board_file()
        attachments = [board_file] if board_file is not None else []

        if interaction is None:
            if self.message:
                await self.message.edit(embed=embed, attachments=attachments, view=self)
            return

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, attachments=attachments, view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=attachments, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This chess game is not yours.", ephemeral=True)
            return False
        return True

    async def finish_game(self, result, line, payout):
        if self.game.finished:
            return
        self.game.finished = True
        self.game.result = result
        self.game.result_line = line
        self.game.payout = int(payout)
        self.game.final_balance = add_user_balance(self.ctx.author.id, payout)
        record_house_profit("chess", self.game.bet_amount, payout, self.ctx.author.id)
        await check_casino_car_pack_role(self.ctx.author, self.ctx)
        ACTIVE_GAME_USERS.discard(self.ctx.author.id)
        self.selected_from = None
        self.selected_moves = []
        self.rebuild_components()

    async def process_move(self, interaction: discord.Interaction, raw_move: str):
        if self.game.finished:
            await interaction.response.send_message("❌ This chess game has already finished.", ephemeral=True)
            return

        legal_moves = chess_generate_legal_moves(self.game.board, "w", self.game.castling)
        selected_move = chess_match_user_move(raw_move, legal_moves)
        if selected_move is None:
            await interaction.response.send_message("❌ That move is not legal from the current position.", ephemeral=True)
            return

        self.selected_from = None
        self.selected_moves = []
        await interaction.response.defer()

        player_captured = self.game.board[selected_move["to"][0]][selected_move["to"][1]]
        self.game.board, self.game.castling = chess_apply_move(self.game.board, selected_move, self.game.castling)
        player_move_text = chess_move_to_text(selected_move)
        self.game.move_history.append(player_move_text)
        if player_captured != ".":
            self.game.white_captures.append(player_captured)
        self.game.last_move = f"You: {player_move_text}"
        self.game.last_move_squares = [selected_move["from"], selected_move["to"]]

        bot_legal = chess_generate_legal_moves(self.game.board, "b", self.game.castling)
        if not bot_legal:
            if chess_in_check(self.game.board, "b"):
                await self.finish_game("win", f"✅ Checkmate. You won **{format_casino_result_display(int(round(self.game.bet_amount * 2.6)), None, self.game.display_bet_amount)} 💵**.", int(round(self.game.bet_amount * 2.6)))
            else:
                await self.finish_game("draw", f"🟨 Stalemate. You got **{format_casino_result_display(int(round(self.game.bet_amount * 1.1)), None, self.game.display_bet_amount)} 💵** back.", int(round(self.game.bet_amount * 1.1)))
            await self.update_message(interaction)
            return

        bot_move = chess_choose_bot_move(self.game)
        if bot_move is None:
            await self.finish_game("draw", f"🟨 Draw. You got **{format_casino_result_display(int(round(self.game.bet_amount * 1.1)), None, self.game.display_bet_amount)} 💵** back.", int(round(self.game.bet_amount * 1.1)))
            await self.update_message(interaction)
            return

        self.game.status = "Bot is thinking..."
        self.rebuild_components()
        await self.update_message(interaction)
        await asyncio.sleep(0.6)

        bot_captured = self.game.board[bot_move["to"][0]][bot_move["to"][1]]
        self.game.board, self.game.castling = chess_apply_move(self.game.board, bot_move, self.game.castling)
        bot_move_text = chess_move_to_text(bot_move)
        self.game.move_history.append(bot_move_text)
        if bot_captured != ".":
            self.game.black_captures.append(bot_captured)
        self.game.last_move = f"You: {player_move_text} • Bot: {bot_move_text}"
        self.game.last_move_squares = [selected_move["from"], selected_move["to"], bot_move["from"], bot_move["to"]]

        player_legal = chess_generate_legal_moves(self.game.board, "w", self.game.castling)
        if not player_legal:
            if chess_in_check(self.game.board, "w"):
                await self.finish_game("loss", f"❌ Checkmate. You lost **{format_casino_result_display(self.game.bet_amount, None, self.game.display_bet_amount)} 💵**.", 0)
            else:
                await self.finish_game("draw", f"🟨 Draw. You got **{format_casino_result_display(int(round(self.game.bet_amount * 1.1)), None, self.game.display_bet_amount)} 💵** back.", int(round(self.game.bet_amount * 1.1)))
        else:
            self.game.status = "Choose a piece, then choose where it moves."
            if chess_in_check(self.game.board, "w"):
                self.game.status = "Your king is in check. Choose a piece, then a legal square."

        self.rebuild_components()
        await self.update_message(interaction)

    async def on_timeout(self):
        if self.game.finished:
            return
        self.game.finished = True
        self.game.result = "loss"
        self.game.result_line = f"⏳ Game timed out. You lost **{format_casino_result_display(self.game.bet_amount, None, self.game.display_bet_amount)} 💵**."
        self.game.final_balance = get_user_balance(self.ctx.author.id)
        record_house_profit("chess", self.game.bet_amount, 0, self.ctx.author.id)
        ACTIVE_GAME_USERS.discard(self.ctx.author.id)
        self.selected_from = None
        self.selected_moves = []
        self.rebuild_components()
        try:
            await self.update_message()
        except Exception:
            pass


@bot.command(name="chess")
async def chess(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Chess"))
        return

    if not await check_betting_cooldown(ctx, "chess", "Chess"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        await ctx.send(embed=build_case_embed("Chess", "❌ You already have an active game running.", 0xE74C3C))
        return

    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !chess",
            description=(
                "**Description:** Start a real playable chess board against the bot\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!chess [bet]\n"
                "**Example:**\n"
                "!chess 1m"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None

    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None or bet_amount <= 0:
        await ctx.send(embed=build_case_embed("Chess", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C))
        return

    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        await ctx.send(embed=build_case_embed("Chess", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C))
        return

    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=build_case_embed("Chess", "❌ Could not remove bet from your balance.", 0xE74C3C))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "chess")

    game = CasinoChessGame(ctx.author.id, bet_amount, display_bet_amount)
    view = CasinoChessView(ctx, game)
    board_file = view.build_board_file()
    if board_file is not None:
        message = await ctx.send(embed=view.build_embed(), file=board_file, view=view)
    else:
        message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message


@bot.command(name="rate")
async def rate(ctx, *, thing: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Rate", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not thing:
        embed = game_embed("Rate", "❌ Usage: `!rate my car build`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    rating = random.randint(1, 10)
    extras = [
        "That is my honest score.",
        "Not bad at all.",
        "There is something to work with there.",
        "That has some real potential."
    ]
    embed = game_embed("📊 Rate", f"I rate **{thing}** a **{rating}/10**.\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)


@bot.command(name="ship")
async def ship(ctx, user1: discord.Member = None, user2: discord.Member = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Ship", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if user1 is None:
        embed = game_embed("Ship", "❌ Usage: `!ship @user` or `!ship @user1 @user2`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if user2 is None:
        user2 = ctx.author

    percentage = random.randint(1, 100)
    if percentage >= 80:
        text = random.choice([
            "💖 Strong match.",
            "💖 That is a dangerously strong match.",
            "💖 There is serious chemistry there."
        ])
    elif percentage >= 50:
        text = random.choice([
            "✨ Could work.",
            "✨ There is definitely something there.",
            "✨ Not bad at all. I can see it."
        ])
    else:
        text = random.choice([
            "💀 Maybe keep it as friends.",
            "💀 Probably best as mates.",
            "💀 The numbers are not being kind there."
        ])

    embed = game_embed("💘 Ship", f"**{user1.display_name}** + **{user2.display_name}** = **{percentage}%**\n{text}")
    await ctx.send(embed=embed)


@bot.command(name="trivia")
async def trivia(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Trivia", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    item = random.choice(TRIVIA_QUESTIONS)
    intro = random.choice([
        "See if you know this one.",
        "Here is your trivia question.",
        "Time for a quick knowledge check.",
        "Let us see how sharp you are."
    ])
    embed = game_embed("🧠 Trivia", f"{intro}\n\n**Question:** {item['q']}\n**Answer:** ||{item['a']}||")
    await ctx.send(embed=embed)


@bot.command(name="fortune")
async def fortune(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Fortune", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    intro = random.choice([
        "Your fortune says:",
        "Here is your fortune:",
        "Today’s message:",
        "Take this with you:"
    ])
    embed = game_embed("🔮 Fortune", f"{intro}\n\n{random.choice(FORTUNES)}")
    await ctx.send(embed=embed)


@bot.command(name="compliment")
async def compliment(ctx, target: discord.Member = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Compliment", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    target = target or ctx.author
    intro = random.choice([
        "A compliment for you:",
        "Here is your boost:",
        "This one is deserved:",
        "You have earned this one:"
    ])
    embed = game_embed("✨ Compliment", f"{intro}\n\n{target.mention}, {random.choice(COMPLIMENTS)}")
    await ctx.send(embed=embed)


@bot.command(name="wyr")
async def wyr(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Would You Rather", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🤷 Would You Rather", random.choice(WOULD_YOU_RATHER))
    await ctx.send(embed=embed)


@bot.command(name="truth")
async def truth(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Truth", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🗣️ Truth", random.choice(TRUTHS))
    await ctx.send(embed=embed)


@bot.command(name="dare")
async def dare(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Dare", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("😈 Dare", random.choice(DARES))
    await ctx.send(embed=embed)


@bot.command(name="emoji")
async def emoji(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Emoji Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("😀 Random Emoji", random.choice(EMOJIS))
    await ctx.send(embed=embed)


@bot.command(name="colourpick")
async def colourpick(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Colour Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🎨 Colour Pick", f"Your colour is **{random.choice(COLOURS)}**.")
    await ctx.send(embed=embed)


@bot.command(name="animalpick")
async def animalpick(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Animal Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🐾 Animal Pick", f"You got: **{random.choice(ANIMALS)}**")
    await ctx.send(embed=embed)


@bot.command(name="foodpick")
async def foodpick(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Food Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🍔 Food Pick", f"Today's pick: **{random.choice(FOODS)}**")
    await ctx.send(embed=embed)


@bot.command(name="carpick")
async def carpick(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Car Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🚗 Car Pick", f"You got: **{random.choice(CARS)}**")
    await ctx.send(embed=embed)


@bot.command(name="countrypick")
async def countrypick(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Country Pick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🌍 Country Pick", f"Destination: **{random.choice(COUNTRIES)}**")
    await ctx.send(embed=embed)


@bot.command(name="superpower")
async def superpower(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Superpower", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🦸 Superpower", f"You unlocked **{random.choice(SUPERPOWERS)}**.")
    await ctx.send(embed=embed)


@bot.command(name="mysterybox")
async def mysterybox(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Mystery Box", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    item = random.choice(MYSTERY_BOX_ITEMS)
    extras = [
        "That is not a bad pull at all.",
        "You definitely got lucky there.",
        "That could have been much worse.",
        "That box had some chaos in it."
    ]
    embed = game_embed("📦 Mystery Box", f"You opened the box and found: **{item}**\n\n{random.choice(extras)}")
    await ctx.send(embed=embed)


@bot.command(name="race")
async def race(ctx, opponent: discord.Member = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Race", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if opponent is None:
        embed = game_embed("Race", "❌ Usage: `!race @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    winner = random.choice([ctx.author, opponent])
    loser = opponent if winner == ctx.author else ctx.author

    race_finish_text = random.choice([
        "won by a bumper at the line.",
        "launched harder and never looked back.",
        "took the lead late and stole the win.",
        "had the cleaner run and finished first.",
        "absolutely gapped the other car.",
        "kept it planted and secured the win.",
        "came through in the final stretch.",
        "had the stronger setup and took it."
    ])

    embed = game_embed(
        "🏁 Race",
        f"**{winner.display_name}** raced **{loser.display_name}** and {race_finish_text}"
    )
    await ctx.send(embed=embed)


@bot.command(name="battle")
async def battle(ctx, opponent: discord.Member = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Battle", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if opponent is None:
        embed = game_embed("Battle", "❌ Usage: `!battle @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    winner = random.choice([ctx.author, opponent])
    loser = opponent if winner == ctx.author else ctx.author

    battle_text = random.choice([
        "outplayed them completely.",
        "held their ground and came out on top.",
        "landed the final hit and won the fight.",
        "stayed calm under pressure and secured the win.",
        "dominated the battle from start to finish.",
        "turned the fight around at the last second.",
        "hit harder when it mattered most.",
        "read the fight perfectly and won."
    ])

    embed = game_embed("⚔️ Battle", f"**{winner.display_name}** {battle_text} **{loser.display_name}**")
    await ctx.send(embed=embed)


@bot.command(name="reverse")
async def reverse(ctx, *, text: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Reverse", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not text:
        embed = game_embed("Reverse", "❌ Usage: `!reverse hello world`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🔁 Reverse", text[::-1])
    await ctx.send(embed=embed)


@bot.command(name="say")
async def say(ctx, *, text: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Say", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not text:
        embed = game_embed("Say", "❌ Usage: `!say hello`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    cleaned = text[:200]
    embed = game_embed("🗨️ Say", cleaned)
    await ctx.send(embed=embed)


@bot.command(name="fact")
async def fact(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Fact", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    facts = [
        "A day on Venus is longer than a year on Venus.",
        "Octopuses have three hearts.",
        "Honey never really spoils.",
        "Bananas are berries, but strawberries are not.",
        "The first car radio was introduced in the 1930s.",
        "Sharks existed before trees."
    ]
    embed = game_embed("📚 Random Fact", random.choice(facts))
    await ctx.send(embed=embed)


@bot.command(name="memeidea")
async def memeidea(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Meme Idea", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("😂 Meme Idea", random.choice(MEME_IDEAS))
    await ctx.send(embed=embed)


@bot.command(name="scramble")
async def scramble(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Scramble", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    word = random.choice(SCRAMBLE_WORDS)
    letters = list(word)
    random.shuffle(letters)
    scrambled = "".join(letters)
    embed = game_embed("🔤 Word Scramble", f"Unscramble this word: **{scrambled}**\nAnswer: ||{word}||")
    await ctx.send(embed=embed)


@bot.command(name="achievement")
async def achievement(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Achievement", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = game_embed("🏆 Achievement Unlocked", f"{ctx.author.mention} — **{random.choice(FAKE_ACHIEVEMENTS)}**")
    await ctx.send(embed=embed)


@bot.command(name="namegen")
async def namegen(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Name Generator", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    first = ["Turbo", "Shadow", "Neon", "Street", "Ghost", "Nitro", "Viper", "Steel", "Blaze", "Drift"]
    second = ["King", "Runner", "Wolf", "Rider", "Machine", "Phantom", "Storm", "Hunter", "Legend", "Bandit"]
    embed = game_embed("🪪 Name Generator", f"Your name is **{random.choice(first)} {random.choice(second)}**")
    await ctx.send(embed=embed)

# =========================================================
# CASINO / BETTING GAMES
# =========================================================
CARD_VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]


def create_shuffled_deck():
    deck = [f"{value}{suit}" for suit in CARD_SUITS for value in CARD_VALUES]
    random.shuffle(deck)
    return deck


def blackjack_card_value(card):
    value = card[:-2] if card.endswith(("♠️", "♥️", "♦️", "♣️")) else card[:-1]
    if value in {"J", "Q", "K"}:
        return 10
    if value == "A":
        return 11
    return int(value)


def blackjack_hand_total(hand):
    total = sum(blackjack_card_value(card) for card in hand)
    aces = sum(1 for card in hand if card.startswith("A"))
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def format_blackjack_hand(hand):
    return " ".join(f"`{card}`" for card in hand)


def hidden_dealer_total(hand):
    visible = [hand[0]]
    return blackjack_hand_total(visible)


def mines_multiplier(safe_hits, mine_count, total_tiles=20):
    multiplier = 1.0
    remaining_tiles = total_tiles
    remaining_safe = total_tiles - mine_count
    for _ in range(safe_hits):
        if remaining_safe <= 0:
            break
        multiplier *= remaining_tiles / remaining_safe
        remaining_tiles -= 1
        remaining_safe -= 1
    return round(multiplier * 1.02, 2)


def casino_denied_embed(title):
    embed = discord.Embed(title=title, description="❌ You do not have permission to use this command.", colour=0xE74C3C, timestamp=now_dt())
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    return embed


class MinesButton(discord.ui.Button):
    def __init__(self, index):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=index // 5)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        await view.reveal_tile(interaction, self.index)


class MinesCashOutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cash Out", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        await view.cash_out(interaction)


class MinesView(discord.ui.View):
    def __init__(self, author, bet_amount, mine_count, ctx=None, display_bet_amount=None):
        super().__init__(timeout=180)
        self.author = author
        self.ctx = ctx
        self.display_bet_amount = display_bet_amount
        self.bet_amount = bet_amount
        self.display_bet_amount = display_bet_amount if display_bet_amount is not None else bet_amount
        self.mine_count = mine_count
        self.total_tiles = 20
        self.safe_hits = 0
        self.finished = False
        self.mine_positions = set(random.sample(range(self.total_tiles), self.mine_count))
        self.first_pick_protected = True
        self.second_pick_soft_protection = True
        self.revealed = set()
        self.jackpot_bonus = roll_mines_jackpot_bonus(self.bet_amount)

        for i in range(self.total_tiles):
            self.add_item(MinesButton(i))
        self.add_item(MinesCashOutButton())

    def build_embed(self, title=None, description=None, colour=0xF1C40F):
        embed = discord.Embed(
            title=title or f"Mines - {format_mines_bet_display(self.display_bet_amount)} 💵",
            description=description or "Avoid the mines hidden in the field to win.",
            colour=colour,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This is not your game.", ephemeral=True)
            return False
        return True

    async def reveal_tile(self, interaction, index):
        if self.finished or index in self.revealed:
            await interaction.response.defer()
            return

        self.revealed.add(index)
        button = next(item for item in self.children if isinstance(item, MinesButton) and item.index == index)
        button.disabled = True

        if index in self.mine_positions:
            protected_pick = False

            if self.first_pick_protected and self.safe_hits == 0:
                protected_pick = True
                self.first_pick_protected = False
            elif self.second_pick_soft_protection and self.safe_hits == 1 and random.random() < 0.55:
                protected_pick = True
                self.second_pick_soft_protection = False

            if protected_pick:
                available_safe_tiles = [i for i in range(self.total_tiles) if i not in self.mine_positions and i != index]
                if available_safe_tiles:
                    relocated_mine = random.choice(available_safe_tiles)
                    self.mine_positions.remove(index)
                    self.mine_positions.add(relocated_mine)
            else:
                button.label = "💣"
                button.style = discord.ButtonStyle.danger
                self.finished = True

                for item in self.children:
                    if isinstance(item, MinesButton):
                        item.disabled = True
                        if item.index in self.mine_positions:
                            item.label = "💣"
                            item.style = discord.ButtonStyle.danger
                        elif item.index in self.revealed:
                            item.label = "💎"
                            item.style = discord.ButtonStyle.success
                ACTIVE_GAME_USERS.discard(self.author.id)
                record_house_profit("mines", self.bet_amount, 0, self.author.id)
                embed = self.build_embed(
                    title="Game Over – You hit a mine",
                    description=f"You lost {format_mines_cashout_result(round_mines_display_amount(self.bet_amount), get_user_balance(self.author.id), self.display_bet_amount)} 💵",
                    colour=0xED4245
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

        self.safe_hits += 1
        button.label = "💎"
        button.style = discord.ButtonStyle.success
        current_multiplier = mines_multiplier(self.safe_hits, self.mine_count, self.total_tiles)
        current_cashout = max(self.bet_amount, int(self.bet_amount * current_multiplier))
        embed = self.build_embed(
            description=(
                f"Avoid the mines hidden in the field to win.\n\n"
                f"**Mines:** {self.mine_count}\n"
                f"**Safe Gems Found:** {self.safe_hits}\n"
                f"**Cash Out Value:** {format_mines_cashout_result(current_cashout, display_bet_amount=self.display_bet_amount)} 💵"
            ),
            colour=0xF1C40F
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def cash_out(self, interaction):
        if self.finished:
            await interaction.response.defer()
            return

        self.finished = True
        payout = max(self.bet_amount, int(self.bet_amount * mines_multiplier(self.safe_hits, self.mine_count, self.total_tiles)))
        total_payout = payout + self.jackpot_bonus
        add_user_balance(self.author.id, total_payout)
        record_house_profit("mines", self.bet_amount, total_payout, self.author.id)
        await check_casino_car_pack_role(self.author, self.ctx)

        for item in self.children:
            if isinstance(item, MinesButton):
                item.disabled = True
                if item.index in self.mine_positions:
                    item.label = "💣"
                    item.style = discord.ButtonStyle.danger
                elif item.index in self.revealed:
                    item.label = "💎"
                    item.style = discord.ButtonStyle.success

        ACTIVE_GAME_USERS.discard(self.author.id)
        updated_balance = get_user_balance(self.author.id)
        embed = self.build_embed(
            title="Cashed Out Successfully",
            description=f"You won {format_mines_cashout_result(total_payout, updated_balance, self.display_bet_amount)} 💵\n\n**Balance:** {format_cash(updated_balance)} 💵",
            colour=0x57F287
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        ACTIVE_GAME_USERS.discard(self.author.id)
        for item in self.children:
            item.disabled = True


class BlackjackView(discord.ui.View):
    def __init__(self, author, bet_amount, display_bet_amount=None):
        super().__init__(timeout=180)
        self.author = author
        self.base_bet = bet_amount
        self.current_bet = bet_amount
        self.display_bet_amount = display_bet_amount
        self.deck = create_shuffled_deck()
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.finished = False
        self.doubled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This is not your game.", ephemeral=True)
            return False
        return True

    def build_embed(self, reveal_dealer=False, result_text=None, result_colour=0xF1C40F):
        player_total = blackjack_hand_total(self.player_hand)
        dealer_cards = self.dealer_hand if reveal_dealer else [self.dealer_hand[0], "??"]
        dealer_total = blackjack_hand_total(self.dealer_hand) if reveal_dealer else hidden_dealer_total(self.dealer_hand)
        embed = discord.Embed(
            title=f"Blackjack - {format_casino_bet_display(display_bet_amount=self.display_bet_amount)} 💵",
            colour=result_colour,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        status_text = result_text or "Choose your move below."
        embed.description = f"{status_text}\n└ Balance: **{format_cash(get_user_balance(self.author.id))} 💵**"
        embed.add_field(name=f"🧑 Player — {player_total}", value=format_blackjack_hand(self.player_hand), inline=True)
        embed.add_field(name=f"🎩 Dealer — {dealer_total}", value=format_blackjack_hand(dealer_cards), inline=True)
        return embed

    def finish_buttons(self):
        for item in self.children:
            item.disabled = True

    async def settle_game(self, interaction):
        while blackjack_hand_total(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        player_total = blackjack_hand_total(self.player_hand)
        dealer_total = blackjack_hand_total(self.dealer_hand)
        if dealer_total > 21 or player_total > dealer_total:
            payout = int(round(self.current_bet * 2.1))
            add_user_balance(self.author.id, payout)
            await check_casino_car_pack_role(self.author, None)
            result = f"✅ You won **{format_casino_result_display(payout, get_user_balance(self.author.id), self.display_bet_amount)} 💵**\n└ Profit: **{format_casino_result_display(payout - self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**"
            colour = 0x57F287
        elif player_total == dealer_total:
            add_user_balance(self.author.id, self.current_bet)
            await check_casino_car_pack_role(self.author, None)
            result = f"🟨 Push — returned **{format_casino_result_display(self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**"
            colour = 0xFEE75C
        else:
            result = f"❌ You lost **{format_casino_result_display(self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**"
            colour = 0xED4245
        self.finished = True
        self.finish_buttons()
        ACTIVE_GAME_USERS.discard(self.author.id)
        await interaction.response.edit_message(embed=self.build_embed(reveal_dealer=True, result_text=result, result_colour=colour), view=self)

    @discord.ui.button(label="🃏 Hit", style=discord.ButtonStyle.primary, row=0)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.defer()
            return
        self.player_hand.append(self.deck.pop())
        if blackjack_hand_total(self.player_hand) > 21:
            self.finished = True
            self.finish_buttons()
            ACTIVE_GAME_USERS.discard(self.author.id)
            embed = self.build_embed(reveal_dealer=True, result_text=f"❌ You busted and lost **{format_casino_result_display(self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**", result_colour=0xED4245)
            await interaction.response.edit_message(embed=embed, view=self)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✅ Stand", style=discord.ButtonStyle.success, row=0)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.defer()
            return
        await self.settle_game(interaction)

    @discord.ui.button(label="💸 Double", style=discord.ButtonStyle.secondary, row=0)
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished or self.doubled:
            await interaction.response.defer()
            return
        ok, _ = remove_user_balance(self.author.id, self.base_bet)
        if not ok:
            await interaction.response.send_message("❌ You do not have enough balance to double down.", ephemeral=True)
            return
        self.current_bet += self.base_bet
        self.doubled = True
        button.disabled = True
        self.player_hand.append(self.deck.pop())
        if blackjack_hand_total(self.player_hand) > 21:
            self.finished = True
            self.finish_buttons()
            ACTIVE_GAME_USERS.discard(self.author.id)
            embed = self.build_embed(reveal_dealer=True, result_text=f"❌ You busted and lost **{format_casino_result_display(self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**", result_colour=0xED4245)
            await interaction.response.edit_message(embed=embed, view=self)
            return
        await self.settle_game(interaction)

    @discord.ui.button(label="🛑 Exit", style=discord.ButtonStyle.danger, row=0)
    async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.defer()
            return
        add_user_balance(self.author.id, self.current_bet)
        await check_casino_car_pack_role(self.author, None)
        self.finished = True
        self.finish_buttons()
        ACTIVE_GAME_USERS.discard(self.author.id)
        embed = self.build_embed(reveal_dealer=True, result_text=f"🟦 Game exited — returned **{format_casino_result_display(self.current_bet, get_user_balance(self.author.id), self.display_bet_amount)} 💵**", result_colour=0x5865F2)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.finished:
            return
        add_user_balance(self.author.id, self.current_bet)
        await check_casino_car_pack_role(self.author, None)
        self.finished = True
        ACTIVE_GAME_USERS.discard(self.author.id)
        self.finish_buttons()


@bot.command(name="balance", aliases=["bal"])
async def balance(ctx, *, member_query: str = None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Balance"))
        return

    if member_query is None:
        member = ctx.author
    else:
        member = await resolve_member_query(ctx, member_query)

    if member is None:
        embed = discord.Embed(
            title="GL Customs",
            description="❌ User not found.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    balance_amount = get_user_balance(member.id)
    embed = discord.Embed(
        title="Cash Balance",
        description=(
            f"{member.mention} has **{format_cash(balance_amount)} 💵**\n"
            f"└ Exact: **{balance_amount:,} 💵**"
        ),
        colour=0xF1C40F,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    await ctx.send(embed=embed)



@bot.command(name="give")
async def give(ctx, *, target_and_amount: str = None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Give"))
        return

    if not target_and_amount:
        embed = discord.Embed(
            title="Command: !give",
            description=(
                "**Description:** Give money to another user\n"
                "**Cooldown:** 3 seconds\n"
                "**Usage:**\n"
                "!give [user] [amount]\n"
                "**Examples:**\n"
                "!give @Zak 100\n"
                "!give Zak 100k\n"
                "!give AB Barnis_154 50k"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    parts = str(target_and_amount).rsplit(" ", 1)
    if len(parts) != 2:
        embed = discord.Embed(
            title="Give",
            description="❌ Usage: `!give [user] [amount]`",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    member_query, amount_raw = parts[0].strip(), parts[1].strip()
    member = await resolve_member_query(ctx, member_query)

    if member is None:
        embed = discord.Embed(
            title="Give",
            description="❌ User not found.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    has_staff_bypass = has_security_permission(ctx.author) or has_infrastructure_permission(ctx.author)

    if ctx.author.id == OWNER_ID:
        try:
            amount = resolve_bet_amount(ctx.author.id, amount_raw)
        except Exception:
            amount = None
    else:
        special_amounts = {"all", "max", "allin", "all-in", "inf", "infinite", "infinity", "∞"}
        if amount_raw.strip().lower() in special_amounts:
            amount = None
        else:
            try:
                amount = parse_cash_amount(amount_raw)
            except Exception:
                amount = None

        if amount is not None and not has_staff_bypass:
            amount = min(amount, MAX_GIVE_AMOUNT)

    if amount is None:
        embed = discord.Embed(
            title="Give",
            description="❌ Invalid amount. Use values like `100000`, `100k`, `5m`, `1b`.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if member.id == ctx.author.id:
        embed = discord.Embed(
            title="Give",
            description="❌ You cannot give money to yourself.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if amount <= 0:
        embed = discord.Embed(
            title="Give",
            description="❌ Amount must be above 0.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if ctx.author.id != OWNER_ID and not has_staff_bypass and amount > MAX_GIVE_AMOUNT:
        amount = MAX_GIVE_AMOUNT

    ok, current_balance = remove_user_balance(ctx.author.id, amount)
    if not ok:
        embed = discord.Embed(
            title="Give",
            description=f"❌ You only have {format_cash(current_balance)} 💵",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    loading = discord.Embed(
        title="Give",
        description=(
            f"💸 Sending **{format_cash(amount)} 💵** to {member.mention}\n"
            f"└ Processing transfer..."
        ),
        colour=0xF1C40F,
        timestamp=now_dt()
    )
    loading.set_footer(text="GL Customs", icon_url=LOGO_URL)
    message = await ctx.send(embed=loading)

    await asyncio.sleep(0.45)

    add_user_balance(member.id, amount)
    await check_casino_car_pack_role(ctx.author, ctx)
    await check_casino_car_pack_role(member, None)

    embed = discord.Embed(
        description=(
            f"✅ You gave **{format_cash(amount)} 💵** to {member.mention}\n"
            f"└ Balance: **{format_cash(get_user_balance(ctx.author.id))} 💵**"
        ),
        colour=0xF1C40F,
        timestamp=now_dt()
    )
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    await message.edit(embed=embed)



@bot.command(name="removecash")
async def removecash(ctx, member: discord.Member = None, amount=None):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Remove Cash", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or amount is None:
        embed = discord.Embed(
            title="Command: !removecash",
            description=(
                "**Description:** Remove money from a user\n"
                "**Cooldown:** 3 seconds\n"
                "**Usage:**\n"
                "!removecash [user] [amount]\n"
                "**Examples:**\n"
                "!removecash @Zak 1000\n"
                "!removecash @Zak all\n"
                "!removecash @Zak inf"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_amount_text = str(amount).strip().lower()
    current_balance = get_user_balance(member.id)

    if raw_amount_text in {"all", "max", "allin", "all-in"}:
        if is_infinite_cash(current_balance):
            removed_amount_display = "∞"
            new_balance = 0
        else:
            removed_amount_display = format_cash(current_balance)
            new_balance = 0

        set_user_balance(member.id, new_balance)
        await check_casino_car_pack_role(member, None)

        embed = discord.Embed(
            title="Remove Cash",
            description=(
                f"✅ Removed **{removed_amount_display} 💵** from {member.mention}\n\n"
                f"**New Balance:** {format_cash(new_balance)} 💵"
            ),
            colour=0xE67E22,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if raw_amount_text in {"inf", "infinite", "infinity", "∞"}:
        if is_infinite_cash(current_balance):
            set_user_balance(member.id, 0)
            await check_casino_car_pack_role(member, None)

            embed = discord.Embed(
                title="Remove Cash",
                description=(
                    f"✅ Removed **∞ 💵** from {member.mention}\n\n"
                    f"**New Balance:** {format_cash(0)} 💵"
                ),
                colour=0xE67E22,
                timestamp=now_dt()
            )
            embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
            await ctx.send(embed=embed)
            return

        embed = build_case_embed("Remove Cash", "❌ That user does not have infinite cash to remove.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        amount = parse_cash_amount(amount)
    except Exception:
        amount = None

    if amount is None:
        embed = build_case_embed("Remove Cash", "❌ Invalid amount. Use values like `100000`, `100k`, `5m`, `1b`, `all`, or `inf`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if amount <= 0:
        embed = build_case_embed("Remove Cash", "❌ Amount must be above 0.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if is_infinite_cash(current_balance):
        embed = build_case_embed("Remove Cash", "❌ That user has infinite cash. Use `all` or `inf` to clear it.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    new_balance = max(0, current_balance - amount)
    set_user_balance(member.id, new_balance)
    await check_casino_car_pack_role(member, None)

    embed = discord.Embed(
        title="Remove Cash",
        description=(
            f"✅ Removed **{format_cash(amount)} 💵** from {member.mention}\n\n"
            f"**New Balance:** {format_cash(new_balance)} 💵"
        ),
        colour=0xE67E22,
        timestamp=now_dt()
    )
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    await ctx.send(embed=embed)

@bot.command(name="admincash")
async def admincash(ctx, member: discord.Member = None, amount=None):
    if not has_infrastructure_permission(ctx.author):
        embed = discord.Embed(
            title="Admin Cash",
            description="❌ You do not have permission to use this command.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs")
        await ctx.send(embed=embed)
        return

    if member is None or amount is None:
        embed = discord.Embed(
            title="Admin Cash",
            description="❌ Usage: `!admincash @user 1000`",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs")
        await ctx.send(embed=embed)
        return

    raw_amount_text = str(amount).strip().lower()
    if raw_amount_text in {"inf", "infinite", "infinity", "∞"}:
        confirmed = await confirm_action(
            ctx,
            "Admin Cash",
            f"This will set {member.mention} to infinite cash."
        )
        if not confirmed:
            return

        set_user_balance(member.id, INFINITE_CASH_VALUE)
        await check_casino_car_pack_role(member, None)

        embed = discord.Embed(
            title="Admin Cash",
            description=(
                f"✅ Set {member.mention} to **infinite cash**.\n\n"
                "**New Balance:** ∞ 💵"
            ),
            colour=0x57F287,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs")
        await ctx.send(embed=embed)
        return

    try:
        amount = parse_cash_amount(amount)
    except Exception:
        amount = None

    if amount is None:
        embed = build_case_embed("Admin Cash", "❌ Invalid amount. Use values like `100000`, `100k`, `5m`, `1b`, or `inf`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if amount <= 0:
        embed = build_case_embed("Admin Cash", "❌ Amount must be above 0.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    new_total = add_user_balance(member.id, amount)
    await check_casino_car_pack_role(member, None)

    embed = discord.Embed(
        title="Admin Cash",
        description=f"✅ Added **{format_cash(amount)} 💵** to {member.mention}\n\n**New Balance:** {format_cash(new_total)} 💵",
        colour=0x57F287,
        timestamp=now_dt()
    )
    embed.set_footer(text="GL Customs")
    await ctx.send(embed=embed)



@bot.command(name="globaladdcash")
async def globaladdcash(ctx, amount=None):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Global Add Cash", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if amount is None:
        embed = build_case_embed("Global Add Cash", "❌ Usage: `!globaladdcash <amount>`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        parsed_amount = parse_cash_amount(amount)
    except Exception:
        parsed_amount = None

    if parsed_amount is None or parsed_amount <= 0:
        embed = build_case_embed("Global Add Cash", "❌ Invalid amount. Use values like `100000`, `100k`, `5m`, `1b`, or `1t`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(
        ctx,
        title="Global Add Cash",
        prompt_text=f"This will add **{format_cash(parsed_amount)} 💵** to every non-bot member with access to the server economy."
    )
    if not confirmed:
        return

    awarded_count = 0
    threshold_hits = 0

    for member in ctx.guild.members:
        if member.bot:
            continue
        if not has_regular_member_permission(member):
            continue

        previous_balance = get_user_balance(member.id)
        add_user_balance(member.id, parsed_amount)
        awarded_count += 1

        if previous_balance < CASINO_CAR_PACK_THRESHOLD <= get_user_balance(member.id):
            threshold_hits += 1

        try:
            await check_casino_car_pack_role(member, None)
        except Exception:
            pass

    embed = build_case_embed(
        "Global Add Cash",
        f"✅ Added **{format_cash(parsed_amount)} 💵** to all eligible members.",
        0x57F287,
        user=ctx.author,
        extra_fields=[
            ("Users Awarded", str(awarded_count), True),
            ("New Casino Reward Unlocks", str(threshold_hits), True)
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="globalresetcash")
async def globalresetcash(ctx):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Global Reset Cash", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(
        ctx,
        title="Global Reset Cash",
        prompt_text="This will reset every saved cash balance to 0. This cannot be undone."
    )
    if not confirmed:
        return

    data = load_data()
    balances = data.setdefault("balances", {})
    affected_users = len(balances)
    balances.clear()
    save_data(data)

    casino_role = ctx.guild.get_role(CASINO_CAR_PACK_ROLE_ID)
    removed_count = 0
    if casino_role is not None:
        for member in ctx.guild.members:
            if casino_role in member.roles:
                try:
                    await member.remove_roles(casino_role, reason=f"Global cash reset by {ctx.author}")
                    removed_count += 1
                except Exception:
                    pass

    embed = build_case_embed(
        "Global Reset Cash",
        f"✅ Reset all saved cash balances to **0**.",
        0x57F287,
        user=ctx.author,
        extra_fields=[
            ("Users Reset", str(affected_users), True),
            ("Casino Car Pack Roles Removed", str(removed_count), True)
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="beg")
async def beg(ctx):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Beg"))
        return

    expiry = get_cooldown_expiry(ctx.author.id, "beg")
    if expiry and expiry > now_dt():
        remaining = format_remaining_time(expiry - now_dt())
        await ctx.send(embed=discord.Embed(
            title="Beg",
            description=f"❌ You can beg again in **{remaining}**.",
            colour=0xE74C3C,
            timestamp=now_dt()
        ))
        return

    streak = update_claim_streak(ctx.author.id, "beg")
    streak_bonus = max(0, streak - 1) * BEG_STREAK_BONUS
    amount = random.randint(1000, 8000) + streak_bonus
    new_balance = add_user_balance(ctx.author.id, amount)
    set_cooldown_expiry(ctx.author.id, "beg", now_dt() + timedelta(hours=12))
    await check_casino_car_pack_role(ctx.author, ctx)

    embed = discord.Embed(
        title="Beg",
        description=(
            f"You received **{format_cash(amount)} 💵**\n"
            f"└ Balance: **{format_cash(new_balance)} 💵**\n"
            f"└ Streak: **{streak}**"
            + (f" (**+{streak_bonus} 💵 bonus**)" if streak_bonus else "")
        ),
        colour=0xF1C40F,
        timestamp=now_dt()
    )
    embed.set_footer(text="GL Customs")
    await ctx.send(embed=embed)

@bot.command(name="work")
async def work(ctx):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Work"))
        return

    expiry = get_cooldown_expiry(ctx.author.id, "work")
    if expiry and expiry > now_dt():
        remaining = format_remaining_time(expiry - now_dt())
        await ctx.send(embed=discord.Embed(
            title="Work",
            description=f"❌ You can work again in **{remaining}**.",
            colour=0xE74C3C,
            timestamp=now_dt()
        ))
        return

    streak = update_claim_streak(ctx.author.id, "work")
    streak_bonus = max(0, streak - 1) * WORK_STREAK_BONUS
    amount = random.randint(3000, 15000) + streak_bonus
    new_balance = add_user_balance(ctx.author.id, amount)
    set_cooldown_expiry(ctx.author.id, "work", now_dt() + timedelta(hours=24))
    await check_casino_car_pack_role(ctx.author, ctx)

    embed = discord.Embed(
        title="Work",
        description=(
            f"You earned **{format_cash(amount)} 💵**\n"
            f"└ Balance: **{format_cash(new_balance)} 💵**\n"
            f"└ Streak: **{streak}**"
            + (f" (**+{streak_bonus} 💵 bonus**)" if streak_bonus else "")
        ),
        colour=0x57F287,
        timestamp=now_dt()
    )
    embed.set_footer(text="GL Customs")
    await ctx.send(embed=embed)

@bot.command(name="mines", aliases=["mine"])
async def mines(ctx, bet_amount=None, mine_count: int = 3):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Mines"))
        return

    if not await check_betting_cooldown(ctx, "mines", "Mines"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        embed = discord.Embed(
            title="Mines",
            description="❌ You already have an active game running.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs",)
        await ctx.send(embed=embed)
        return

    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !mines",
            description=(
                "**Description:** Play mines and win money\n"
                "**Cooldown:** 3 seconds\n"
                "**Usage:**\n"
                "!mines [bet] [mines]\n"
                "**Example:**\n"
                "!mines 100 3"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs")
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount

    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None

    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None:
        embed = build_case_embed("Mines", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if bet_amount <= 0:
        await ctx.send(embed=discord.Embed(title="Mines", description="❌ Bet must be above 0.", colour=0xE74C3C, timestamp=now_dt()))
        return

    if mine_count < 1 or mine_count > 10:
        await ctx.send(embed=discord.Embed(title="Mines", description="❌ Mine count must be between 1 and 10.", colour=0xE74C3C, timestamp=now_dt()))
        return

    ok, current_balance = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=discord.Embed(title="Mines", description=f"❌ You only have {format_cash(current_balance)} 💵", colour=0xE74C3C, timestamp=now_dt()))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "mines")
    try:
        pre = await send_game_premessage(
            ctx,
            f"Mines - {format_mines_bet_display(display_bet_amount if display_bet_amount is not None else bet_amount)} 💵",
            "💣 Planting mines...",
            "🟩 Building your board..."
        )
        view = MinesView(ctx.author, bet_amount, mine_count, ctx, display_bet_amount=display_bet_amount)
        await asyncio.sleep(0.35)
        await pre.edit(embed=view.build_embed(), view=view)
    except Exception:
        add_user_balance(ctx.author.id, bet_amount)
        ACTIVE_GAME_USERS.discard(ctx.author.id)
        raise


@bot.command(name="bj", aliases=["blackjack"])
async def bj(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Blackjack"))
        return

    if not await check_betting_cooldown(ctx, "bj", "Blackjack"):
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        embed = discord.Embed(
            title="Blackjack",
            description="❌ You already have an active game running.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if bet_amount is None:
        await ctx.send(embed=discord.Embed(title="Blackjack", description="❌ Usage: `!bj <bet>`", colour=0xE74C3C, timestamp=now_dt()))
        return

    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None:
        await ctx.send(embed=discord.Embed(title="Blackjack", description="❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", colour=0xE74C3C, timestamp=now_dt()))
        return

    if bet_amount <= 0:
        await ctx.send(embed=discord.Embed(title="Blackjack", description="❌ Bet must be above 0.", colour=0xE74C3C, timestamp=now_dt()))
        return

    ok, current_balance = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        await ctx.send(embed=discord.Embed(title="Blackjack", description=f"❌ You only have {format_cash(current_balance)} 💵", colour=0xE74C3C, timestamp=now_dt()))
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "bj")
    try:
        pre = await send_game_premessage(
            ctx,
            f"Blackjack - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            "🃏 Shuffling deck...",
            "🂠 Dealing opening hands..."
        )
        view = BlackjackView(ctx.author, bet_amount, display_bet_amount=display_bet_amount)
        await asyncio.sleep(0.35)
        await pre.edit(embed=view.build_embed(), view=view)
    except Exception:
        add_user_balance(ctx.author.id, bet_amount)
        ACTIVE_GAME_USERS.discard(ctx.author.id)
        raise


@bot.command(name="rewards")
async def rewards(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed("Rewards", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="Rewards",
        description=(
            "**Weekly Leaderboard Payouts**\n"
            f"🥇 **#1:** {format_cash(WEEKLY_REWARD_AMOUNTS[1])} 💵\n"
            f"🥈 **#2:** {format_cash(WEEKLY_REWARD_AMOUNTS[2])} 💵\n"
            f"🥉 **#3:** {format_cash(WEEKLY_REWARD_AMOUNTS[3])} 💵\n\n"
            "**Streak Bonuses**\n"
            f"`!beg` gives **+{format_cash(BEG_STREAK_BONUS)} 💵** extra per streak level after the first.\n"
            f"`!work` gives **+{format_cash(WORK_STREAK_BONUS)} 💵** extra per streak level after the first.\n"
            f"Streaks reset after **{STREAK_RESET_HOURS} hours** without claiming.\n\n"
            "**Casino Car Pack**\n"
            f"Reach **{format_cash(CASINO_CAR_PACK_THRESHOLD)} 💵** to unlock the **Casino Car Pack** role automatically.\n"
            f"Role awarded: <@&{CASINO_CAR_PACK_ROLE_ID}>\n"
            "Reward: a dedicated **pack of 5 cars**.\n\n"
            "**Casino Commands**\n"
            "`!slots`, `!roulette`, `!crash`, `!rocket`, `!dice`, `!baccarat`, `!plinko`, `!mines`, `!bj`, `!chess`, `!profit`\n\n"
            "**Mines Jackpot**\n"
            f"`!mines` has a **{int(MINES_JACKPOT_CHANCE * 100)}%** jackpot chance on cash out.\n"
            f"Jackpot range: **{format_cash(MINES_JACKPOT_MIN)} - {format_cash(MINES_JACKPOT_MAX)} 💵**"
        ),
        colour=0xF1C40F,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    await ctx.send(embed=embed)


@bot.command(name="mystats")
async def mystats(ctx, *, member_query: str = None):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed("My Stats", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    member = ctx.author if member_query is None else await resolve_member_query(ctx, member_query)
    if member is None:
        embed = build_case_embed("My Stats", "❌ User not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    stats = get_casino_user_stats(member.id)
    fav_game = "None"
    game_counts = stats.get("game_counts", {})
    if game_counts:
        fav_game = max(game_counts.items(), key=lambda item: item[1])[0]

    net_value = int(stats.get("net", 0))
    result_colour = 0x57F287 if net_value >= 0 else 0xE74C3C

    embed = discord.Embed(
        title="Casino Player Stats",
        description=(
            f"**Player:** {member.mention}\n"
            f"**Wagered:** {format_cash(stats.get('wagered', 0))} 💵\n"
            f"**Paid Out:** {format_cash(stats.get('paid_out', 0))} 💵\n"
            f"**Net Result:** {format_cash(net_value)} 💵\n"
            f"**Games Played:** {stats.get('plays', 0)}\n"
            f"**Favourite Game:** {fav_game}\n"
            f"**Biggest Win:** {format_cash(stats.get('biggest_win', 0))} 💵"
        ),
        colour=result_colour,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs Casino", icon_url=LOGO_URL)
    await ctx.send(embed=embed)


@bot.command(name="profit")
async def profit(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed("Casino Stats", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    profit_data = get_profit_data()
    totals = profit_data.get("totals", {})
    history = profit_data.get("history", [])

    total_wagered = sum(int(v.get("wagered", 0)) for v in totals.values())
    total_paid_out = sum(int(v.get("paid_out", 0)) for v in totals.values())
    house_profit = total_wagered - total_paid_out
    house_edge = (house_profit / total_wagered) if total_wagered > 0 else 0.0

    today_key = now_dt().strftime("%Y-%m-%d")
    today = next((item for item in history if item.get("date") == today_key), None)
    today_wagered = int(today.get("wagered", 0)) if today else 0
    today_paid = int(today.get("paid_out", 0)) if today else 0
    today_profit = int(today.get("house_profit", 0)) if today else 0

    bar = build_profit_bar(min(max(house_edge, 0.0), 0.20) / 0.20, width=18)

    recent_days = history[-7:]
    values = [max(0, int(x.get("house_profit", 0))) for x in recent_days]
    graph = build_profit_sparkline(values)

    game_lines = []
    top_games = sorted(
        totals.items(),
        key=lambda item: int(item[1].get("wagered", 0)),
        reverse=True
    )[:5]

    for name, stats in top_games:
        game_lines.append(
            f"`{name}` → wagered {format_cash(int(stats.get('wagered', 0)))} • house {format_cash(int(stats.get('house_profit', 0)))}"
        )

    embed = discord.Embed(
        title="Casino Stats",
        description=(
            f"**House Edge**\n"
            f"`{bar}` **{house_edge * 100:.2f}%**\n\n"
            f"**Today**\n"
            f"• Wagered: **{format_cash(today_wagered)} 💵**\n"
            f"• Paid Out: **{format_cash(today_paid)} 💵**\n"
            f"• Profit: **{format_cash(today_profit)} 💵**\n\n"
            f"**All Time**\n"
            f"• Wagered: **{format_cash(total_wagered)} 💵**\n"
            f"• Paid Out: **{format_cash(total_paid_out)} 💵**\n"
            f"• Profit: **{format_cash(house_profit)} 💵**\n\n"
            f"**Last 7 Days**\n"
            f"```{graph}```"
        ),
        colour=0x2ECC71,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs Casino", icon_url=LOGO_URL)

    embed.add_field(
        name="Top Games",
        value="\n".join(game_lines) if game_lines else "No data yet.",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name="vehiclehelp")
async def vehiclehelp(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed("Vehicle Help", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="Vehicle Help",
        description="Here is the compatibility information for GL Customs vehicles.",
        colour=0x3498DB,
        timestamp=now_dt()
    )
    embed.set_author(name="GL Customs", icon_url=LOGO_URL)
    embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
    embed.add_field(name="Compatibility", value="These vehicles are **FiveM ready only**.", inline=False)
    embed.add_field(name="ELS", value="These vehicles are **non-ELS**.", inline=False)
    embed.add_field(name="Important", value="They are only compatible with **FiveM**.", inline=False)
    embed.add_field(name="How to Install", value="Drag and drop the vehicle folder into your server's **resources** folder, then make sure the resource name matches the folder name.", inline=False)
    embed.add_field(name="How to Start It", value="Start the vehicle through **txAdmin** by using `ensure foldername` in your server config or by starting the resource from the txAdmin console.", inline=False)
    embed.add_field(name="Need Help?", value="If you need help installing the vehicle or have any questions, please open a **support ticket**.", inline=False)
    await ctx.send(embed=embed)


# =========================================================
# ROLESTRIP
# =========================================================
@bot.command(name="rolestrip")
async def rolestrip(ctx, *args):
    owner_self_bypass = False
    if args:
        if args[0].lower() == "restore":
            if len(args) >= 2:
                target_id = parse_user_id_input(args[1])
                owner_self_bypass = ctx.author.id == OWNER_ID and target_id == OWNER_ID
        else:
            target_id = parse_user_id_input(args[0])
            owner_self_bypass = ctx.author.id == OWNER_ID and target_id == OWNER_ID

    if not owner_self_bypass and not has_rolestrip_permission(ctx.author):
        embed = build_case_embed("Role Strip", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if len(args) < 1:
        embed = build_case_embed(
            "Role Strip",
            "❌ Usage: `!rolestrip @user [reason]` or `!rolestrip restore @user`",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    if args[0].lower() == "restore":
        if len(args) < 2:
            embed = build_case_embed("Role Restore", "❌ Usage: `!rolestrip restore @user`", 0xE74C3C)
            await ctx.send(embed=embed)
            return

        try:
            target = await commands.MemberConverter().convert(ctx, args[1])
        except commands.MemberNotFound:
            embed = build_case_embed("Role Restore", "❌ User not found.", 0xE74C3C)
            await ctx.send(embed=embed)
            return

        saved_roles = get_rolestrip_roles(target.id)
        if not saved_roles:
            embed = build_case_embed("Role Restore", "❌ No saved roles found for that user.", 0xE74C3C, user=target)
            await ctx.send(embed=embed)
            return

        author_highest = ctx.author.top_role.position
        bot_highest = ctx.guild.me.top_role.position
        restored_mentions = []

        for role_id in saved_roles:
            role = ctx.guild.get_role(role_id)
            if not role:
                continue
            if not owner_self_bypass and role.position >= author_highest:
                continue
            if role.position >= bot_highest:
                continue
            try:
                await target.add_roles(role, reason=f"Role restore by {ctx.author}")
                restored_mentions.append(role.mention)
            except (discord.Forbidden, discord.HTTPException):
                pass

        delete_rolestrip_roles(target.id)

        if not restored_mentions:
            embed = build_case_embed("Role Restore", "❌ No roles could be restored.", 0xE74C3C, user=target)
            await ctx.send(embed=embed)
            return

        case_id = next_case_id("rolestrip_case")
        record_case(case_id, "ROLE RESTORE", target.id, ctx.author.id, "Roles restored")
        embed = build_case_embed(
            "Role Restore",
            "The user's saved roles have been restored.",
            0x2ECC71,
            case_id=case_id,
            user=target,
            extra_fields=[("Roles Restored", "\n".join(restored_mentions), False)]
        )
        await ctx.send(embed=embed)
        await send_modlog(embed)
        return

    try:
        target = await commands.MemberConverter().convert(ctx, args[0])
    except commands.MemberNotFound:
        embed = build_case_embed("Role Strip", "❌ User not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(
        ctx,
        "Role Strip",
        f"This will remove all removable roles from {target.mention}."
    )
    if not confirmed:
        return

    if not owner_self_bypass:
        ok, msg = can_moderate(ctx.author, target)
        if not ok:
            embed = build_case_embed("Role Strip", msg, 0xE74C3C, user=target)
            await ctx.send(embed=embed)
            return

    reason = " ".join(args[1:]).strip()
    author_highest = ctx.author.top_role.position
    bot_highest = ctx.guild.me.top_role.position
    removed_ids = []
    removed_mentions = []

    for role in target.roles:
        if role.id == ctx.guild.id:
            continue
        if role.managed:
            continue
        if role.id in PROTECTED_ROLE_IDS:
            continue
        if not owner_self_bypass and role.position >= author_highest:
            continue
        if role.position >= bot_highest:
            continue
        removed_ids.append(role.id)
        removed_mentions.append(role.mention)

    if not removed_ids:
        embed = build_case_embed("Role Strip", "❌ No removable roles found.", 0xE74C3C, user=target)
        await ctx.send(embed=embed)
        return

    save_rolestrip_roles(target.id, removed_ids)

    roles_to_remove = [ctx.guild.get_role(rid) for rid in removed_ids]
    roles_to_remove = [r for r in roles_to_remove if r is not None]

    try:
        await target.remove_roles(*roles_to_remove, reason=f"Role strip by {ctx.author}: {reason or 'No reason provided'}")
    except discord.Forbidden:
        embed = build_case_embed("Role Strip", "❌ I do not have permission to remove one or more of those roles.", 0xE74C3C, user=target)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("rolestrip_case")
    record_case(case_id, "ROLESTRIP", target.id, ctx.author.id, reason or "None")

    public_embed = build_case_embed(
        "Role Strip",
        f"Successfully stripped roles from {target.mention}.",
        0xE74C3C,
        case_id=case_id,
        user=target,
        reason=reason if reason else "None"
    )
    await ctx.send(embed=public_embed)

    log_embed = build_case_embed(
        "Role Strip",
        "The user's roles have been removed.",
        0xE74C3C,
        case_id=case_id,
        user=target,
        reason=reason if reason else "None",
        extra_fields=[("Roles Removed", "\n".join(removed_mentions), False)]
    )
    await send_modlog(log_embed)

# =========================================================
# BLACKLIST / UNBLACKLIST
# =========================================================
@bot.command(name="blacklist")
async def blacklist(ctx, member: discord.Member = None, *, reason=""):
    owner_self_bypass = ctx.author.id == OWNER_ID and member is not None and member.id == OWNER_ID

    if not owner_self_bypass and not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Blacklist", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Blacklist", "❌ Usage: `!blacklist @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Blacklist", "This is a dangerous action.")
    if not confirmed:
        return

    if not owner_self_bypass:
        ok, msg = can_moderate(ctx.author, member)
        if not ok:
            embed = build_case_embed("Blacklist", msg, 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

    bot_highest = ctx.guild.me.top_role.position
    removed_ids = []
    removed_mentions = []

    for role in member.roles:
        if role.id == ctx.guild.id:
            continue
        if role.managed:
            continue
        if role.id == BLACKLISTED_ROLE_ID:
            continue
        if role.position >= bot_highest:
            continue
        removed_ids.append(role.id)
        removed_mentions.append(role.mention)

    save_blacklist_roles(member.id, removed_ids)

    roles_to_remove = [ctx.guild.get_role(rid) for rid in removed_ids]
    roles_to_remove = [r for r in roles_to_remove if r is not None]
    blacklist_role = ctx.guild.get_role(BLACKLISTED_ROLE_ID)

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Blacklist by {ctx.author}: {reason or 'None'}")
        if blacklist_role:
            await member.add_roles(blacklist_role, reason=f"Blacklist by {ctx.author}: {reason or 'None'}")
    except discord.Forbidden:
        embed = build_case_embed("Blacklist", "❌ I do not have permission to update that user's roles.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("blacklist_case")
    record_case(case_id, "BLACKLIST", member.id, ctx.author.id, reason if reason else "None")

    embed = build_case_embed(
        "Blacklist",
        f"The user has been blacklisted and assigned <@&{BLACKLISTED_ROLE_ID}>.",
        0xE74C3C,
        case_id=case_id,
        user=member,
        reason=reason if reason else "None",
        extra_fields=[("Roles Removed", "\n".join(removed_mentions) if removed_mentions else "None", False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="unblacklist")
async def unblacklist(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Unblacklist", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Unblacklist", "❌ Usage: `!unblacklist @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    saved_roles = get_blacklist_roles(member.id)
    if not saved_roles:
        embed = build_case_embed("Unblacklist", "❌ No saved roles found for that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    bot_highest = ctx.guild.me.top_role.position
    restored_mentions = []

    try:
        blacklist_role = ctx.guild.get_role(BLACKLISTED_ROLE_ID)
        if blacklist_role:
            await member.remove_roles(blacklist_role, reason=f"Unblacklist by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Unblacklist", "❌ I do not have permission to remove the blacklisted role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    for role_id in saved_roles:
        role = ctx.guild.get_role(role_id)
        if not role:
            continue
        if role.position >= bot_highest:
            continue
        try:
            await member.add_roles(role, reason=f"Unblacklist by {ctx.author}")
            restored_mentions.append(role.mention)
        except (discord.Forbidden, discord.HTTPException):
            pass

    delete_blacklist_roles(member.id)
    case_id = next_case_id("unblacklist_case")
    record_case(case_id, "UNBLACKLIST", member.id, ctx.author.id, "User unblacklisted")

    embed = build_case_embed(
        "Unblacklist",
        "The user has been unblacklisted and previous roles restored.",
        0x2ECC71,
        case_id=case_id,
        user=member,
        extra_fields=[("Roles Restored", "\n".join(restored_mentions) if restored_mentions else "None", False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# ALLROLES
# =========================================================
@bot.command(name="allroles")
async def allroles(ctx, member: discord.Member = None):
    owner_self_bypass = ctx.author.id == OWNER_ID and member is not None and member.id == OWNER_ID

    if not owner_self_bypass and not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("All Roles", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("All Roles", "❌ Usage: `!allroles @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "All Roles", f"This will assign all eligible roles to {member.mention}.")
    if not confirmed:
        return

    staff_cap_position = get_staff_cap_position(ctx.guild)
    if staff_cap_position is None:
        embed = build_case_embed("All Roles", "❌ Staff cap role not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not owner_self_bypass:
        ok, msg = can_moderate(ctx.author, member)
        if not ok:
            embed = build_case_embed("All Roles", msg, 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

    bot_highest = ctx.guild.me.top_role.position
    roles_to_add = []
    given_mentions = []

    for role in ctx.guild.roles:
        if role.id == ctx.guild.id:
            continue
        if role.managed:
            continue
        if role.id in BLOCKED_ROLE_IDS:
            continue
        if role.position >= staff_cap_position:
            continue
        if role.position >= bot_highest:
            continue
        if role in member.roles:
            continue

        roles_to_add.append(role)
        given_mentions.append(role.mention)

    if not roles_to_add:
        embed = build_case_embed("All Roles", "❌ No eligible roles could be given.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.add_roles(*roles_to_add, reason=f"All roles given by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("All Roles", "❌ I do not have permission to give one or more of those roles.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("allroles_case")
    record_case(case_id, "ALLROLES", member.id, ctx.author.id, "All eligible roles assigned")

    embed = build_case_embed(
        "All Roles",
        f"All eligible roles have been assigned to {member.mention}.",
        0x2ECC71,
        case_id=case_id,
        user=member,
        extra_fields=[("Roles Given", "\n".join(given_mentions), False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# ROLEREQ
# =========================================================
@bot.command(name="rolereq")
async def rolereq(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not has_regular_member_permission(ctx.author):
        embed = build_case_embed(
            "Role Request",
            "❌ You do not have permission to use this command.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    roles = get_requestable_roles(ctx.guild, ctx.author)

    if not roles:
        embed = build_case_embed(
            "Role Request",
            "❌ There are no roles available for you to request right now.",
            0xE74C3C,
            user=ctx.author
        )
        await ctx.send(embed=embed)
        return

    embed = build_role_request_list_embed(ctx.author, roles, page=0)
    view = RoleRequestStartView(ctx.author, roles, page=0)
    await ctx.send(embed=embed, view=view)

# =========================================================
# ROLEADD / ROLEREMOVE / TEMPROLE
# =========================================================
@bot.command(name="roleadd", aliases=["role"])
async def roleadd(ctx, member: discord.Member = None, *, role_name=None):
    if not has_role_command_permission(ctx.author):
        embed = build_case_embed("Give Role", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or role_name is None:
        embed = build_case_embed("Give Role", "❌ Usage: `!roleadd @user role name` or `!role @user @role`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = role_lookup_case_insensitive(ctx.guild, role_name)
    if not role:
        embed = build_case_embed("Give Role", "❌ Role not found. You can use a role name, role ID or role mention.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Give Role", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    if not has_role_command_bypass(ctx.author):
        if role.id == ctx.guild.id or role.managed or is_dangerous_role(role):
            embed = build_case_embed("Give Role", "❌ That role cannot be assigned with this command.", 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

        staff_cap_position = get_staff_cap_position(ctx.guild)
        if staff_cap_position is None:
            embed = build_case_embed("Give Role", "❌ Staff cap role not found.", 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

        if role.position >= staff_cap_position:
            embed = build_case_embed("Give Role", "❌ That role is above the allowed cap.", 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

    if role.position >= ctx.guild.me.top_role.position:
        embed = build_case_embed("Give Role", "❌ My bot role must be above that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    if role in member.roles:
        embed = build_case_embed("Give Role", "❌ That user already has that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.add_roles(role, reason=f"Role given by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Give Role", "❌ I cannot assign that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("roleadd_case")
    record_case(case_id, "ROLEADD", member.id, ctx.author.id, f"Role: {role.name}")

    embed = build_case_embed(
        "Give Role",
        f"The role **{role.name}** has been assigned.",
        0x2ECC71,
        case_id=case_id,
        user=member,
        extra_fields=[("Role Given", role.name, False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="roleremove")
async def roleremove(ctx, member: discord.Member = None, *, role_name=None):
    if not has_role_command_permission(ctx.author):
        embed = build_case_embed("Remove Role", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or role_name is None:
        embed = build_case_embed("Remove Role", "❌ Usage: `!roleremove @user role name`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = role_lookup_case_insensitive(ctx.guild, role_name)
    if not role:
        embed = build_case_embed("Remove Role", "❌ Role not found.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Remove Role", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    if not has_role_command_bypass(ctx.author):
        if role.id in PROTECTED_ROLE_IDS:
            embed = build_case_embed("Remove Role", "❌ That role cannot be removed with this command.", 0xE74C3C, user=member)
            await ctx.send(embed=embed)
            return

    if role.position >= ctx.guild.me.top_role.position:
        embed = build_case_embed("Remove Role", "❌ My bot role must be above that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    if role not in member.roles:
        embed = build_case_embed("Remove Role", "❌ That user does not have that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Remove Role", "❌ I cannot remove that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("roleremove_case")
    record_case(case_id, "ROLEREMOVE", member.id, ctx.author.id, f"Role: {role.name}")

    embed = build_case_embed(
        "Remove Role",
        f"The role **{role.name}** has been removed.",
        0xE67E22,
        case_id=case_id,
        user=member,
        extra_fields=[("Role Removed", role.name, False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="temprole")
async def temprole(ctx, member: discord.Member = None, *, role_and_duration=None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Temporary Role", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or role_and_duration is None:
        embed = build_case_embed(
            "Temporary Role",
            "❌ Usage: `!temprole @user role name [duration]`\nExamples:\n`!temprole @user customer`\n`!temprole @user customer 1h`",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    role_and_duration = role_and_duration.strip()
    parts = role_and_duration.rsplit(" ", 1)

    if len(parts) == 2 and parse_duration(parts[1]) is not None:
        role_name = parts[0].strip()
        duration = parts[1].strip()
    else:
        role_name = role_and_duration
        duration = "1h"

    delta = parse_duration(duration)
    if delta is None:
        embed = build_case_embed("Temporary Role", "❌ Invalid duration. Example: `10m`, `2h`, `1d`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = role_lookup_case_insensitive(ctx.guild, role_name)
    if not role:
        embed = build_case_embed("Temporary Role", "❌ Role not found.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Temporary Role", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    if not has_role_command_bypass(ctx.author):
        if role.id == ctx.guild.id or role.managed or is_dangerous_role(role):
            embed = build_case_embed(
                "Temporary Role",
                "❌ That role cannot be assigned with this command.",
                0xE74C3C,
                user=member
            )
            await ctx.send(embed=embed)
            return

        staff_cap_position = get_staff_cap_position(ctx.guild)
        if staff_cap_position is None:
            embed = build_case_embed(
                "Temporary Role",
                "❌ Staff cap role not found.",
                0xE74C3C,
                user=member
            )
            await ctx.send(embed=embed)
            return

        if role.position >= staff_cap_position:
            embed = build_case_embed(
                "Temporary Role",
                "❌ That role is above the allowed cap.",
                0xE74C3C,
                user=member
            )
            await ctx.send(embed=embed)
            return

    if role.position >= ctx.guild.me.top_role.position:
        embed = build_case_embed("Temporary Role", "❌ My bot role must be above that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.add_roles(role, reason=f"Temporary role by {ctx.author} for {duration}")
    except discord.Forbidden:
        embed = build_case_embed("Temporary Role", "❌ I cannot assign that role.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    expires_at = now_dt() + delta
    add_temp_role(member.id, ctx.guild.id, role.id, ctx.author.id, expires_at.isoformat())

    case_id = next_case_id("temprole_case")
    record_case(case_id, "TEMPROLE", member.id, ctx.author.id, f"Role: {role.name} | Duration: {duration}")

    embed = build_case_embed(
        "Temporary Role",
        f"The role **{role.name}** has been assigned temporarily.",
        0x3498DB,
        case_id=case_id,
        user=member,
        extra_fields=[
            ("Role", role.name, True),
            ("Duration", duration, True),
            ("Expires", expires_at.strftime("%d-%m-%Y %H:%M"), False)
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# KICK / BAN / UNBAN / GBAN / UNGBAN
# =========================================================
@bot.command(name="kick")
async def kick(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Kick", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Kick", "❌ Usage: `!kick @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Kick", "This is a dangerous action.")
    if not confirmed:
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Kick", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.kick(reason=f"Kick by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Kick", "❌ I do not have permission to kick that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("kick_case")
    record_case(case_id, "KICK", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Kick",
        "The user has been kicked from the server.",
        0xE67E22,
        case_id=case_id,
        user=member,
        reason=reason
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="ban")
async def ban(ctx, target_input: str = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Ban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    target_member, target_id, target_kind = await resolve_ban_target(ctx, target_input)

    if target_kind == "missing":
        embed = build_case_embed("Ban", "❌ Usage: `!ban @user/user_id [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if target_kind == "invalid" or target_id is None:
        embed = build_case_embed("Ban", "❌ I could not find that user. Use a mention or a valid user ID.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if target_id == ctx.author.id:
        embed = build_case_embed("Ban", "❌ You cannot ban yourself.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return

    if target_id == bot.user.id:
        embed = build_case_embed("Ban", "❌ You cannot ban the bot.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Ban", "This is a dangerous action.")
    if not confirmed:
        return

    if target_member is not None:
        ok, msg = can_moderate(ctx.author, target_member)
        if not ok:
            embed = build_case_embed("Ban", msg, 0xE74C3C, user=target_member)
            await ctx.send(embed=embed)
            return

    try:
        await ctx.guild.ban(discord.Object(id=target_id), reason=f"Ban by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Ban", "❌ I do not have permission to ban that user.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return
    except discord.HTTPException:
        embed = build_case_embed("Ban", "❌ I could not ban that user ID.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("ban_case")
    record_case(case_id, "BAN", target_id, ctx.author.id, reason)

    embed = build_case_embed(
        "Ban",
        "The user has been banned from this server.",
        0xC0392B,
        case_id=case_id,
        user=target_member,
        user_id=target_id if target_member is None else None,
        reason=reason
    )

    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="unban")
async def unban(ctx, user_id: int = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Unban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if user_id is None:
        embed = build_case_embed("Unban", "❌ Usage: `!unban user_id [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if is_globally_banned(user_id) and ctx.author.id not in UNBAN_GBAN_BYPASS_USER_IDS and ctx.author.id != ctx.guild.owner_id:
        embed = build_case_embed(
            "Unban",
            "❌ That user is globally banned. You cannot unban them with `!unban`.",
            0xE74C3C,
            user_id=user_id
        )
        await ctx.send(embed=embed)
        return

    user_obj = discord.Object(id=user_id)

    try:
        await ctx.guild.unban(user_obj, reason=f"Unban by {ctx.author} | {reason}")
    except discord.NotFound:
        embed = build_case_embed("Unban", "❌ That user is not banned here.", 0xE74C3C, user_id=user_id)
        await ctx.send(embed=embed)
        return
    except discord.Forbidden:
        embed = build_case_embed("Unban", "❌ I do not have permission to unban that user.", 0xE74C3C, user_id=user_id)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("unban_case")
    record_case(case_id, "UNBAN", user_id, ctx.author.id, reason)

    embed = build_case_embed(
        "Unban",
        "The user has been unbanned from this server.",
        0x2ECC71,
        case_id=case_id,
        user_id=user_id,
        reason=reason
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="gban")
async def gban(ctx, target_input: str = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Global Ban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    target_member, target_id, target_kind = await resolve_ban_target(ctx, target_input)

    if target_kind == "missing":
        embed = build_case_embed("Global Ban", "❌ Usage: `!gban @user/user_id [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if target_kind == "invalid" or target_id is None:
        embed = build_case_embed("Global Ban", "❌ I could not find that user. Use a mention or a valid user ID.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if target_id == ctx.author.id:
        embed = build_case_embed("Global Ban", "❌ You cannot globally ban yourself.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return

    if target_id == bot.user.id:
        embed = build_case_embed("Global Ban", "❌ You cannot globally ban the bot.", 0xE74C3C, user_id=target_id)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Global Ban", "This is a dangerous action.")
    if not confirmed:
        return

    if target_member is not None:
        ok, msg = can_moderate(ctx.author, target_member)
        if not ok:
            embed = build_case_embed("Global Ban", msg, 0xE74C3C, user=target_member)
            await ctx.send(embed=embed)
            return

    add_global_ban(target_id, ctx.author.id, reason)
    success_guilds = []
    failed_guilds = []

    for guild in bot.guilds:
        try:
            await guild.ban(discord.Object(id=target_id), reason=f"GBAN by {ctx.author} | {reason}")
            success_guilds.append(guild.name)
        except (discord.Forbidden, discord.HTTPException):
            failed_guilds.append(guild.name)

    case_id = next_case_id("gban_case")
    record_case(case_id, "GBAN", target_id, ctx.author.id, reason)

    extra_fields = [("Guilds Banned In", "\n".join(success_guilds) if success_guilds else "None", False),
        ("Guilds Failed", "\n".join(failed_guilds) if failed_guilds else "None", False)]
    if target_member is None:
        extra_fields.insert(0, ("Target Type", "User ID / Outside Server", True))

    embed = build_case_embed(
        "Global Ban",
        "The user has been globally banned from GL Customs and connected servers.",
        0xC0392B,
        case_id=case_id,
        user=target_member,
        reason=reason,
        user_id=target_id if target_member is None else None,
        extra_fields=extra_fields
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="ungban")
async def ungban(ctx, user_id: int = None):
    if not has_security_or_infrastructure_permission(ctx.author) and ctx.author.id not in UNBAN_GBAN_BYPASS_USER_IDS and ctx.author.id != ctx.guild.owner_id:
        embed = build_case_embed("Un-Global Ban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if user_id is None:
        embed = build_case_embed("Un-Global Ban", "❌ Usage: `!ungban user_id`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    removed = remove_global_ban(user_id)
    success_guilds = []
    failed_guilds = []

    for guild in bot.guilds:
        try:
            await guild.unban(discord.Object(id=user_id), reason=f"Un-GBAN by {ctx.author}")
            success_guilds.append(guild.name)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            failed_guilds.append(guild.name)

    if not removed and not success_guilds:
        embed = build_case_embed("Un-Global Ban", "❌ No global ban entry found for that user ID.", 0xE74C3C, user_id=user_id)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("ungban_case")
    record_case(case_id, "UNGBAN", user_id, ctx.author.id, "Global ban removed")

    embed = build_case_embed(
        "Un-Global Ban",
        "The global ban has been removed.",
        0x2ECC71,
        case_id=case_id,
        user_id=user_id,
        extra_fields=[
            ("Guilds Unbanned In", "\n".join(success_guilds) if success_guilds else "None", False),
            ("Guilds Failed", "\n".join(failed_guilds) if failed_guilds else "None", False),
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# LOCK / UNLOCK / LOCKDOWN / UNLOCKDOWN / SLOWMODE / PURGE
# =========================================================
@bot.command(name="lock")
async def lock(ctx, channel: discord.TextChannel = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Lock", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)

    raw_state, exists = get_lock_state(ctx.guild.id, channel.id)
    if not exists:
        save_lock_state(ctx.guild.id, channel.id, overwrite.send_messages)

    overwrite.send_messages = False

    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Locked by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Lock", "❌ I do not have permission to lock that channel.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("lock_case")
    record_case(case_id, "LOCK", ctx.author.id, ctx.author.id, f"Channel locked: {channel.id}")

    embed = build_case_embed(
        "Lock",
        f"{channel.mention} has been locked.",
        0xE67E22,
        case_id=case_id
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="unlock")
async def unlock(ctx, channel: discord.TextChannel = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Unlock", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    raw_state, exists = get_lock_state(ctx.guild.id, channel.id)

    if not exists:
        embed = build_case_embed(
            "Unlock",
            "❌ No saved lock state found for that channel. I won't unlock it blindly.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    overwrite.send_messages = normalise_saved_bool(raw_state)

    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Unlocked by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Unlock", "❌ I do not have permission to unlock that channel.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    delete_lock_state(ctx.guild.id, channel.id)

    case_id = next_case_id("unlock_case")
    record_case(case_id, "UNLOCK", ctx.author.id, ctx.author.id, f"Channel unlocked: {channel.id}")

    embed = build_case_embed(
        "Unlock",
        f"{channel.mention} has been unlocked.",
        0x2ECC71,
        case_id=case_id
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="lockdown")
async def lockdown(ctx):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Lockdown", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Lockdown", "This will lock the entire server.")
    if not confirmed:
        return

    saved_states = {}
    locked = 0

    for channel in ctx.guild.text_channels:
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        saved_states[str(channel.id)] = overwrite.send_messages
        overwrite.send_messages = False
        try:
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Server lockdown by {ctx.author}")
            locked += 1
        except Exception:
            pass

    save_lockdown_state(ctx.guild.id, saved_states)

    case_id = next_case_id("lockdown_case")
    record_case(case_id, "LOCKDOWN", ctx.guild.id, ctx.author.id, f"Locked {locked} channels")

    embed = build_case_embed(
        "Lockdown",
        "Server lockdown activated.",
        0xC0392B,
        case_id=case_id,
        extra_fields=[("Channels Locked", str(locked), True)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="unlockdown")
async def unlockdown(ctx):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Unlockdown", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    saved_states, exists = get_lockdown_state(ctx.guild.id)
    if not exists:
        embed = build_case_embed(
            "Unlockdown",
            "❌ No saved lockdown state found. I won't unlock channels blindly.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    restored = 0

    for channel in ctx.guild.text_channels:
        if str(channel.id) not in saved_states:
            continue

        overwrite = channel.overwrites_for(ctx.guild.default_role)
        raw_value = saved_states[str(channel.id)]
        overwrite.send_messages = normalise_saved_bool(raw_value)

        try:
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Server unlockdown by {ctx.author}")
            restored += 1
        except Exception:
            pass

    delete_lockdown_state(ctx.guild.id)

    case_id = next_case_id("unlockdown_case")
    record_case(case_id, "UNLOCKDOWN", ctx.guild.id, ctx.author.id, f"Restored {restored} channels")

    embed = build_case_embed(
        "Unlockdown",
        "Server lockdown removed and previous channel states restored.",
        0x2ECC71,
        case_id=case_id,
        extra_fields=[("Channels Restored", str(restored), True)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="slowmode")
async def slowmode(ctx, seconds: int = None, channel: discord.TextChannel = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Slowmode", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if seconds is None or seconds < 0 or seconds > 21600:
        embed = build_case_embed("Slowmode", "❌ Usage: `!slowmode seconds [#channel]` (0-21600)", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    channel = channel or ctx.channel
    try:
        await channel.edit(slowmode_delay=seconds, reason=f"Slowmode changed by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Slowmode", "❌ I do not have permission to edit that channel.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("slowmode_case")
    record_case(case_id, "SLOWMODE", ctx.guild.id, ctx.author.id, f"{channel.id} -> {seconds}s")

    embed = build_case_embed(
        "Slowmode",
        f"Slowmode has been set for {channel.mention}.",
        0x3498DB,
        case_id=case_id,
        extra_fields=[("Delay", f"{seconds} seconds", True)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="purge")
async def purge(ctx, amount: int = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Purge", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if amount is None or amount < 1 or amount > 200:
        embed = build_case_embed(
            "Purge",
            "❌ Usage: `!purge amount` (1-200)\nThis deletes exactly that many messages, plus your command message automatically.",
            0xE74C3C
        )
        await ctx.send(embed=embed)
        return

    if amount >= 50:
        confirmed = await confirm_action(ctx, "Purge", "Large purge detected.")
        if not confirmed:
            return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        deleted_count = max(len(deleted) - 1, 0)
    except discord.Forbidden:
        embed = build_case_embed("Purge", "❌ I do not have permission to purge messages here.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("purge_case")
    record_case(case_id, "PURGE", ctx.guild.id, ctx.author.id, f"{deleted_count} messages in {ctx.channel.id}")

    embed = build_case_embed(
        "Purge",
        f"Deleted **{deleted_count}** messages in {ctx.channel.mention}.",
        0x3498DB,
        case_id=case_id,
        extra_fields=[("Channel", ctx.channel.mention, True)]
    )

    msg = await ctx.send(embed=embed)
    await send_modlog(embed)

    try:
        await msg.delete(delay=3)
    except discord.HTTPException:
        pass

# =========================================================
# WARN / WARNINGS / CLEARWARNS / NOTE / NOTES / CLEARNOTES
# =========================================================
@bot.command(name="warn")
async def warn(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Warn", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Warn", "❌ Usage: `!warn @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Warn", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    warn_count = add_warning(member.id, ctx.author.id, reason)
    case_id = next_case_id("warn_case")
    record_case(case_id, "WARN", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Warn",
        "The user has been warned.",
        0xF1C40F,
        case_id=case_id,
        user=member,
        reason=reason,
        extra_fields=[("Total Warnings", str(warn_count), False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="warnings")
async def warnings(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Warnings", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Warnings", "❌ Usage: `!warnings @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    user_warnings = get_warnings(member.id)
    if not user_warnings:
        embed = build_case_embed("Warnings", "This user has no warnings.", 0x2ECC71, user=member)
        await ctx.send(embed=embed)
        return

    lines = []
    for idx, warning in enumerate(user_warnings, start=1):
        lines.append(f"**{idx}.** {warning['reason']} — <@{warning['staff_id']}> — {warning['date']}")

    embed = build_case_embed(
        "Warnings",
        f"Warning history for {member.mention}.",
        0xF1C40F,
        user=member,
        extra_fields=[
            ("Total", str(len(user_warnings)), True),
            ("Entries", "\n".join(lines[:10]), False),
        ]
    )
    await ctx.send(embed=embed)


@bot.command(name="clearwarns")
async def clearwarns(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Clear Warnings", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Clear Warnings", "❌ Usage: `!clearwarns @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    clear_warnings(member.id)
    case_id = next_case_id("clearwarns_case")
    record_case(case_id, "CLEARWARNS", member.id, ctx.author.id, "All warnings cleared")

    embed = build_case_embed(
        "Clear Warnings",
        "All warnings have been cleared for this user.",
        0x2ECC71,
        case_id=case_id,
        user=member
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="note")
async def note(ctx, member: discord.Member = None, *, note_text=""):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Note", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or not note_text:
        embed = build_case_embed("Note", "❌ Usage: `!note @user note text`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    total = add_note(member.id, ctx.author.id, note_text)
    case_id = next_case_id("note_case")
    record_case(case_id, "NOTE", member.id, ctx.author.id, note_text)

    embed = build_case_embed(
        "Note",
        "A staff note has been added for this user.",
        0x3498DB,
        case_id=case_id,
        user=member,
        extra_fields=[
            ("Note", note_text, False),
            ("Total Notes", str(total), False)
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="notes")
async def notes(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Notes", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Notes", "❌ Usage: `!notes @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    user_notes = get_notes(member.id)
    if not user_notes:
        embed = build_case_embed("Notes", "This user has no staff notes.", 0x2ECC71, user=member)
        await ctx.send(embed=embed)
        return

    lines = []
    for idx, note_item in enumerate(user_notes, start=1):
        lines.append(f"**{idx}.** {note_item['note']} — <@{note_item['staff_id']}> — {note_item['date']}")

    embed = build_case_embed(
        "Notes",
        f"Staff notes for {member.mention}.",
        0x3498DB,
        user=member,
        extra_fields=[
            ("Total", str(len(user_notes)), True),
            ("Entries", "\n".join(lines[:10]), False),
        ]
    )
    await ctx.send(embed=embed)


@bot.command(name="clearnotes")
async def clearnotes(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Clear Notes", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Clear Notes", "❌ Usage: `!clearnotes @user`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    clear_notes(member.id)
    case_id = next_case_id("clearnotes_case")
    record_case(case_id, "CLEARNOTES", member.id, ctx.author.id, "All notes cleared")

    embed = build_case_embed(
        "Clear Notes",
        "All staff notes have been cleared for this user.",
        0x2ECC71,
        case_id=case_id,
        user=member
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# TIMEOUT / UNTIMEOUT / MUTE / UNMUTE
# =========================================================
@bot.command(name="timeout")
async def timeout(ctx, member: discord.Member = None, duration=None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Timeout", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or duration is None:
        embed = build_case_embed("Timeout", "❌ Usage: `!timeout @user 10m [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Timeout", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    delta = parse_duration(duration)
    if delta is None:
        embed = build_case_embed("Timeout", "❌ Invalid duration. Example: `10m`, `2h`, `1d`", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    until = now_dt() + delta

    try:
        await member.edit(timed_out_until=until, reason=f"Timeout by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Timeout", "❌ I do not have permission to timeout that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("timeout_case")
    record_case(case_id, "TIMEOUT", member.id, ctx.author.id, f"{reason} | Duration: {duration}")

    embed = build_case_embed(
        "Timeout",
        "The user has been timed out.",
        0xE67E22,
        case_id=case_id,
        user=member,
        reason=reason,
        extra_fields=[("Duration", duration, True)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="untimeout")
async def untimeout(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Untimeout", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Untimeout", "❌ Usage: `!untimeout @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        await member.edit(timed_out_until=None, reason=f"Untimeout by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Untimeout", "❌ I do not have permission to remove that timeout.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("untimeout_case")
    record_case(case_id, "UNTIMEOUT", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Untimeout",
        "The user's timeout has been removed.",
        0x2ECC71,
        case_id=case_id,
        user=member,
        reason=reason
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="mute")
async def mute(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Mute", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Mute", "❌ Usage: `!mute @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not role:
        embed = build_case_embed("Mute", "❌ Muted role not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        await member.add_roles(role, reason=f"Mute by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Mute", "❌ I do not have permission to mute that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("mute_case")
    record_case(case_id, "MUTE", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Mute",
        "The user has been muted.",
        0xE67E22,
        case_id=case_id,
        user=member,
        reason=reason
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="unmute")
async def unmute(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Unmute", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Unmute", "❌ Usage: `!unmute @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = ctx.guild.get_role(MUTED_ROLE_ID)
    if not role:
        embed = build_case_embed("Unmute", "❌ Muted role not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        await member.remove_roles(role, reason=f"Unmute by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Unmute", "❌ I do not have permission to unmute that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("unmute_case")
    record_case(case_id, "UNMUTE", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Unmute",
        "The user has been unmuted.",
        0x2ECC71,
        case_id=case_id,
        user=member,
        reason=reason
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)

# =========================================================
# NICK / CLEAN / AUDIT LOG
# =========================================================
@bot.command(name="nickname")
async def nickname(ctx, member: discord.Member = None, *, new_name=None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Nickname", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or new_name is None:
        embed = build_case_embed("Nickname", "❌ Usage: `!nickname @user new nickname`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        await member.edit(nick=new_name, reason=f"Nickname changed by {ctx.author}")
    except discord.Forbidden:
        embed = build_case_embed("Nickname", "❌ I do not have permission to change that nickname.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("nickname_case")
    record_case(case_id, "NICKNAME", member.id, ctx.author.id, f"New nickname: {new_name}")

    embed = build_case_embed(
        "Nickname",
        "The user's nickname has been changed.",
        0x3498DB,
        case_id=case_id,
        user=member,
        extra_fields=[("New Nickname", new_name, False)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="clean")
async def clean(ctx, amount: int = 25):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Clean", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if amount < 1 or amount > 200:
        embed = build_case_embed("Clean", "❌ Usage: `!clean amount` (1-200)", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author == bot.user or m.author == ctx.author)
    except discord.Forbidden:
        embed = build_case_embed("Clean", "❌ I do not have permission to clean messages here.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("clean_case")
    record_case(case_id, "CLEAN", ctx.guild.id, ctx.author.id, f"{max(len(deleted)-1, 0)} messages cleaned")

    embed = build_case_embed(
        "Clean",
        f"Cleaned **{len(deleted) - 1}** matching messages in {ctx.channel.mention}.",
        0x3498DB,
        case_id=case_id
    )
    msg = await ctx.send(embed=embed)
    await send_modlog(embed)
    try:
        await msg.delete(delay=5)
    except discord.HTTPException:
        pass


@bot.command(name="auditlog")
async def auditlog(ctx):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Audit Log", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    logs = []

    try:
        async for entry in ctx.guild.audit_logs(limit=50):
            logs.append(f"{entry.created_at} | {entry.user} | {entry.action} | {entry.target}")
    except discord.Forbidden:
        embed = build_case_embed("Audit Log", "❌ I do not have permission to view the audit log.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if not logs:
        await ctx.send("No audit log entries found.")
        return

    file_data = io.StringIO("\n".join(logs))
    discord_file = discord.File(io.BytesIO(file_data.getvalue().encode("utf-8")), filename="auditlog.txt")
    await ctx.send(file=discord_file)

# =========================================================
# CASES / HISTORY / EDIT CASE
# =========================================================
@bot.command(name="case")
async def case_lookup(ctx, case_id: int = None):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Case Lookup", "❌ Permission denied.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if case_id is None:
        embed = build_case_embed("Case Lookup", "❌ Usage: !case case_id", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    data = load_data()
    case = data["cases"].get(str(case_id))

    if not case:
        embed = build_case_embed("Case Lookup", "❌ Case not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    timeline = case.get("timeline", [])
    timeline_lines = []
    for item in timeline[-5:]:
        if item.get("type") == "created":
            timeline_lines.append(f"{item['date']} • Created • {item.get('reason', 'None')}")
        else:
            timeline_lines.append(f"{item['date']} • {item.get('type', 'event').title()} • {item.get('text', '')}")

    embed = build_case_embed(
        f"Case {case_id}",
        f"Action: **{case['action']}**",
        0x3498DB,
        case_id=case_id,
        extra_fields=[
            ("User ID", case["user_id"], True),
            ("Staff ID", case["staff_id"], True),
            ("Reason", case["reason"], False),
            ("Date", case["date"], False),
            ("Timeline", "\n".join(timeline_lines) if timeline_lines else "No timeline entries.", False)
        ]
    )

    await ctx.send(embed=embed)


@bot.command(name="history")
async def history(ctx, member: discord.Member = None):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("History", "❌ Permission denied.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("History", "❌ Usage: !history @user", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    data = load_data()

    cases = []
    for cid, case in data["cases"].items():
        if case["user_id"] == str(member.id):
            cases.append((cid, case))

    if not cases:
        embed = build_case_embed("History", "No cases found.", 0x2ECC71, user=member)
        await ctx.send(embed=embed)
        return

    cases.sort(key=lambda x: int(x[0]), reverse=True)

    lines = []
    for cid, case in cases[:10]:
        lines.append(f"**Case {cid}** • {case['action']} • {case['reason']}")

    embed = build_case_embed(
        "User History",
        f"Moderation history for {member.mention}",
        0x3498DB,
        user=member,
        extra_fields=[
            ("Cases", "\n".join(lines), False)
        ]
    )

    await ctx.send(embed=embed)


@bot.command(name="editcase")
async def editcase(ctx, case_id: int = None, *, new_reason=None):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Edit Case", "❌ Permission denied.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if case_id is None or new_reason is None:
        embed = build_case_embed("Edit Case", "❌ Usage: !editcase case_id new reason", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    data = load_data()
    case = data["cases"].get(str(case_id))

    if not case:
        embed = build_case_embed("Edit Case", "❌ Case not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    old_reason = case.get("reason", "None")
    case["reason"] = new_reason
    case["edited_by"] = str(ctx.author.id)
    case["edited_at"] = now_str()
    case.setdefault("timeline", []).append({
        "type": "edited",
        "staff_id": str(ctx.author.id),
        "text": f"Reason changed from '{old_reason}' to '{new_reason}'",
        "date": now_str()
    })

    save_data(data)

    embed = build_case_embed(
        "Case Updated",
        f"Case **{case_id}** has been edited.",
        0x3498DB,
        case_id=case_id,
        extra_fields=[
            ("Old Reason", old_reason, False),
            ("New Reason", new_reason, False)
        ]
    )

    await ctx.send(embed=embed)
    await send_modlog(embed)
# =========================================================
@bot.command(name="plinko")
async def plinko(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Plinko"))
        return
    if not await check_betting_cooldown(ctx, "plinko", "Plinko"):
        return
    if ctx.author.id in ACTIVE_GAME_USERS:
        embed = discord.Embed(title="Plinko", description="⏳ Please wait a moment before starting another game.", colour=0xE67E22, timestamp=now_dt())
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return
    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !plinko",
            description=(
                "**Description:** Drop a ball in plinko and win money\n"
                f"**Cooldown:** {BETTING_COOLDOWN_SECONDS} seconds\n"
                "**Usage:**\n"
                "!plinko [bet/all]\n"
                "**Example:**\n"
                "!plinko all"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return
    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None
    if bet_amount is None:
        embed = build_case_embed("Plinko", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return
    if bet_amount <= 0:
        embed = build_case_embed("Plinko", "❌ Bet amount must be above 0.", 0xE74C3C)
        await ctx.send(embed=embed)
        return
    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        embed = build_case_embed("Plinko", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C)
        await ctx.send(embed=embed)
        return
    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        embed = build_case_embed("Plinko", "❌ Could not remove bet from your balance.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    start_betting_cooldown(ctx.author.id, "plinko")

    try:
        width = len(PLINKO_MULTIPLIERS)
        rows_count = 10
        center = width // 2
        slot_index = random.choices(
            population=list(range(width)),
            weights=[1, 2, 4, 6, 8, 9, 8, 6, 4, 2, 1],
            k=1
        )[0]
        multiplier = PLINKO_MULTIPLIERS[slot_index]
        payout = int(round(bet_amount * multiplier))
        new_balance = add_user_balance(ctx.author.id, payout)
        record_house_profit("plinko", bet_amount, payout, ctx.author.id)
        await check_casino_car_pack_role(ctx.author, ctx)

        def row_columns(row_index):
            active_cols = min(width, 3 + row_index)
            start = max(0, center - (active_cols // 2))
            end = min(width - 1, start + active_cols - 1)
            if end - start + 1 < active_cols:
                start = max(0, end - active_cols + 1)
            return list(range(start, end + 1))

        positions = []
        current_col = center
        drift = random.choice([-1, 1])

        for row_index in range(rows_count):
            valid_cols = row_columns(row_index)
            if row_index == 0:
                current_col = min(valid_cols, key=lambda c: abs(c - current_col))
                positions.append(current_col)
                continue

            if random.random() < 0.68:
                candidate = current_col + drift
            else:
                drift *= -1
                candidate = current_col + drift

            candidate = max(min(valid_cols), min(max(valid_cols), candidate))

            if candidate not in valid_cols:
                candidate = min(valid_cols, key=lambda c: abs(c - candidate))

            current_col = candidate
            positions.append(current_col)

        positions[-1] = slot_index

        visual_path = []
        for row_index in range(rows_count - 1):
            start_col = float(positions[row_index])
            end_col = float(positions[row_index + 1])

            visual_path.append((float(row_index), start_col))

            curve_strength = 0.22 if end_col > start_col else -0.22 if end_col < start_col else 0.0

            for blend in ():
                interp_row = row_index + blend
                interp_col = start_col + ((end_col - start_col) * blend)

                if curve_strength != 0.0:
                    arc = (1 - ((blend - 0.5) ** 2) * 4)
                    interp_col += curve_strength * arc

                visual_path.append((interp_row, interp_col))

        visual_path.append((float(rows_count - 1), float(positions[-1])))

        def render_frame(path_row, path_col, landed=False):
            rows = []
            for r in range(rows_count):
                valid_cols = row_columns(r)
                cells = []
                for c in range(width):
                    if c in valid_cols:
                        if abs(path_row - r) <= 0.34 and round(path_col) == c:
                            cells.append("🔵")
                        else:
                            cells.append("•")
                    else:
                        cells.append("·")
                rows.append(" ".join(cells))

            mults = []
            for i, m in enumerate(PLINKO_MULTIPLIERS):
                label = f"{m}x"
                if i == slot_index:
                    mults.append(f"✨**[{label}]**✨" if landed else f"**[{label}]**")
                else:
                    mults.append(label)

            return "\n".join(rows) + "\n\n" + " ".join(mults)

        embed = discord.Embed(
            title=f"Plinko - {format_casino_bet_display(display_bet_amount=display_bet_amount)} 💵",
            description=render_frame(visual_path[0][0], visual_path[0][1]),
            colour=0x5865F2,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        message = await ctx.send(embed=embed)

        reduced_path = []
        last_whole_row = -1
        for path_row, path_col in visual_path[1:]:
            whole_row = int(path_row)
            if (whole_row != last_whole_row and whole_row % 2 == 0) or path_row == visual_path[-1][0]:
                reduced_path.append((path_row, path_col))
                last_whole_row = whole_row

        for i, (path_row, path_col) in enumerate(reduced_path[:-1]):
            await asyncio.sleep(0.0015)
            embed.description = render_frame(path_row, path_col)
            await message.edit(embed=embed)

        embed.description = (
            render_frame(visual_path[-1][0], visual_path[-1][1], landed=True)
            + f"\n\nYou landed on **{multiplier}x**\n"
            + f"└ Won: **{format_casino_result_display(payout, new_balance, display_bet_amount)} 💵**\n"
            + f"└ Balance: **{format_cash(new_balance)} 💵**"
        )
        embed.colour = 0x57F287 if multiplier >= 1 else 0xE67E22
        await message.edit(embed=embed)
    except Exception:
        add_user_balance(ctx.author.id, bet_amount)
        raise
    finally:
        ACTIVE_GAME_USERS.discard(ctx.author.id)

# =========================================================


class RoleRequestApprovalView(discord.ui.View):
    def __init__(self, requester: discord.Member, role: discord.Role):
        super().__init__(timeout=None)
        self.requester = requester
        self.role = role

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not has_security_or_infrastructure_permission(interaction.user):
            await interaction.response.send_message(
                "❌ Only Security Team or Infrastructure can approve or deny role requests.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Approve Role Request", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ Guild not found.", ephemeral=True)
            return

        member = guild.get_member(self.requester.id)
        role = guild.get_role(self.role.id)

        if member is None:
            await interaction.response.send_message("❌ Requester is no longer in the server.", ephemeral=True)
            return

        if role is None:
            await interaction.response.send_message("❌ That role no longer exists.", ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message("❌ That user already has this role.", ephemeral=True)
            return

        requestable_roles = get_requestable_roles(guild, member)
        if role.id not in {r.id for r in requestable_roles}:
            await interaction.response.send_message(
                "❌ That role is no longer eligible to be requested or assigned.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason=f"Approved role request by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I do not have permission to assign that role.",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Failed to assign that role.",
                ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True

        case_id = next_case_id("rolereq_case")
        record_case(case_id, "ROLEREQ APPROVED", member.id, interaction.user.id, f"Role: {role.name}")

        approved_embed = build_role_request_embed(
            requester=member,
            role=role,
            approver_text=interaction.user.mention,
            status_text="Approved ✅",
            colour=0x2ECC71,
            case_id=case_id,
            decision_text=f"✅ Role request approved by {interaction.user.mention}."
        )
        approved_embed.description = f"✅ Role request approved for {member.mention}."

        await interaction.response.edit_message(embed=approved_embed, view=self)
        await send_modlog(approved_embed)

    @discord.ui.button(label="Deny Role Request", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ Guild not found.", ephemeral=True)
            return

        member = guild.get_member(self.requester.id) or self.requester
        role = guild.get_role(self.role.id) or self.role

        for child in self.children:
            child.disabled = True

        case_id = next_case_id("rolereq_case")
        record_case(case_id, "ROLEREQ DENIED", member.id, interaction.user.id, f"Role: {role.name}")

        denied_embed = build_role_request_embed(
            requester=member,
            role=role,
            approver_text=interaction.user.mention,
            status_text="Denied ❌",
            colour=0xE74C3C,
            case_id=case_id,
            decision_text=f"❌ Role request denied by {interaction.user.mention}."
        )
        denied_embed.description = f"❌ Role request denied for {member.mention}."

        await interaction.response.edit_message(embed=denied_embed, view=self)
        await send_modlog(denied_embed)


def build_role_request_list_embed(requester, roles, page=0):
    total_pages = max(1, (len(roles) + ROLE_REQUEST_PAGE_SIZE - 1) // ROLE_REQUEST_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * ROLE_REQUEST_PAGE_SIZE
    end = start + ROLE_REQUEST_PAGE_SIZE
    page_roles = roles[start:end]

    embed = build_case_embed(
        "Role Request",
        "Select a role from the dropdown below to submit a request.",
        0x3498DB,
        user=requester,
        extra_fields=[
            ("Available Roles", "\n".join(role.mention for role in page_roles) if page_roles else "No roles available.", False),
            ("Page", f"{page + 1}/{total_pages}", False),
        ]
    )
    return embed


class RoleRequestSelect(discord.ui.Select):
    def __init__(self, requester: discord.Member, roles, page: int = 0):
        self.requester = requester
        self.all_roles = roles
        self.page = page

        start = page * ROLE_REQUEST_PAGE_SIZE
        end = start + ROLE_REQUEST_PAGE_SIZE
        self.roles = roles[start:end]

        options = [
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id),
                description=f"Request {role.name}"[:100]
            )
            for role in self.roles
        ]

        if not options:
            options = [discord.SelectOption(label="No roles available", value="0")]

        super().__init__(
            placeholder="Choose a role to request...",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not bool(self.roles)
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ Only the requester can use this menu.",
                ephemeral=True
            )
            return

        selected_role_id = int(self.values[0])
        if selected_role_id == 0:
            await interaction.response.send_message(
                "❌ There are no roles available on this page.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(selected_role_id)

        if role is None:
            await interaction.response.send_message(
                "❌ That role could not be found.",
                ephemeral=True
            )
            return

        embed = build_role_request_embed(self.requester, role)
        view = RoleRequestApprovalView(self.requester, role)

        try:
            await interaction.response.defer()
        except discord.HTTPException:
            return

        await interaction.channel.send(embed=embed, view=view)

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass


class RoleRequestStartView(discord.ui.View):
    def __init__(self, requester: discord.Member, roles, page: int = 0):
        super().__init__(timeout=120)
        self.requester = requester
        self.roles = roles
        self.page = page
        self.total_pages = max(1, (len(roles) + ROLE_REQUEST_PAGE_SIZE - 1) // ROLE_REQUEST_PAGE_SIZE)
        self.refresh_items()

    def refresh_items(self):
        self.clear_items()
        self.add_item(RoleRequestSelect(self.requester, self.roles, self.page))
        self.add_item(RoleRequestPrevButton())
        self.add_item(RoleRequestNextButton())

        for item in self.children:
            if isinstance(item, RoleRequestPrevButton):
                item.disabled = self.page <= 0
            elif isinstance(item, RoleRequestNextButton):
                item.disabled = self.page >= self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ Only the person who used the command can choose a role.",
                ephemeral=True
            )
            return False
        return True


class RoleRequestPrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Previous", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, RoleRequestStartView):
            return

        if view.page > 0:
            view.page -= 1
            view.refresh_items()

        embed = build_role_request_list_embed(view.requester, view.roles, view.page)
        await interaction.response.edit_message(embed=embed, view=view)


class RoleRequestNextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, RoleRequestStartView):
            return

        if view.page < view.total_pages - 1:
            view.page += 1
            view.refresh_items()

        embed = build_role_request_list_embed(view.requester, view.roles, view.page)
        await interaction.response.edit_message(embed=embed, view=view)

class AdvancedHelpView(discord.ui.View):
    def __init__(self, member: discord.Member, active_page: str = "home"):
        super().__init__(timeout=None)
        self.member = member
        self.message = None
        self.active_page = active_page
        self._apply_button_styles()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    def _apply_button_styles(self):
        for attr in [
            "home_button", "vehicle_button", "games_button", "utility_button",
            "economy_button", "rewards_button", "security_button", "infrastructure_button"
        ]:
            if hasattr(self, attr):
                getattr(self, attr).style = discord.ButtonStyle.secondary

        if self.active_page == "home" and hasattr(self, "home_button"):
            self.home_button.style = discord.ButtonStyle.primary
        elif self.active_page == "vehicle" and hasattr(self, "vehicle_button"):
            self.vehicle_button.style = discord.ButtonStyle.primary
        elif self.active_page == "games" and hasattr(self, "games_button"):
            self.games_button.style = discord.ButtonStyle.primary
        elif self.active_page == "utility" and hasattr(self, "utility_button"):
            self.utility_button.style = discord.ButtonStyle.primary
        elif self.active_page == "economy" and hasattr(self, "economy_button"):
            self.economy_button.style = discord.ButtonStyle.primary
        elif self.active_page == "rewards" and hasattr(self, "rewards_button"):
            self.rewards_button.style = discord.ButtonStyle.primary
        elif self.active_page == "security" and hasattr(self, "security_button"):
            self.security_button.style = discord.ButtonStyle.danger
        elif self.active_page == "infrastructure" and hasattr(self, "infrastructure_button"):
            self.infrastructure_button.style = discord.ButtonStyle.danger

    def _get_current_embed(self):
        if self.active_page == "home":
            return self.build_home_embed()
        if self.active_page == "vehicle":
            return self.build_vehicle_embed()
        if self.active_page == "games":
            return self.build_games_embed()
        if self.active_page == "utility":
            return self.build_utility_embed()
        if self.active_page == "economy":
            return self.build_economy_embed()
        if self.active_page == "rewards":
            return self.build_rewards_embed()
        if self.active_page == "security":
            return self.build_security_embed()
        if self.active_page == "infrastructure":
            return self.build_infra_embed()
        return self.build_home_embed()

    async def _refresh_without_edit(self, interaction: discord.Interaction):
        new_view = AdvancedHelpView(interaction.user, active_page=self.active_page)
        new_view.message = interaction.message
        await interaction.response.edit_message(
            embed=new_view._get_current_embed(),
            view=new_view
        )

    def build_home_embed(self):
        embed = discord.Embed(
            title="GL Customs Help Menu",
            description=(
                "Use the buttons below to browse command categories.\n\n"
                "**Access is filtered automatically based on your role permissions.**"
            ),
            colour=0x3498DB,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

        embed.add_field(
            name="🎮 Games",
            value="Fun commands, randomisers, battles, and leaderboard features.",
            inline=False
        )
        embed.add_field(
            name="🛠️ Utility",
            value="Payment info, bot information, and general member tools.",
            inline=False
        )
        embed.add_field(
            name="🚗 Vehicle Support",
            value="Vehicle compatibility, install steps, and txAdmin startup instructions.",
            inline=False
        )
        embed.add_field(
            name="🎰 Casino",
            value="Casino games and cash commands.",
            inline=False
        )
        embed.add_field(
            name="🎁 Rewards",
            value="Reward progression, bonuses, and the Casino Car Pack unlock.",
            inline=False
        )
        embed.add_field(
            name="🔐 Security",
            value="Moderation tools for Security and Infrastructure staff only.",
            inline=False
        )
        embed.add_field(
            name="🏗️ Infrastructure",
            value="Advanced moderation and system tools for Infrastructure only.",
            inline=False
        )
        return embed

    def build_vehicle_embed(self):
        embed = discord.Embed(
            title="🚗 Vehicle Support",
            description="Here is the compatibility information for GL Customs vehicles.",
            colour=0x3498DB,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        embed.add_field(name="Compatibility", value="These vehicles are **FiveM ready only**.", inline=False)
        embed.add_field(name="ELS", value="These vehicles are **non-ELS**.", inline=False)
        embed.add_field(name="Important", value="They are only compatible with **FiveM**.", inline=False)
        embed.add_field(name="How to Install", value="Drag and drop the vehicle folder into your server's **resources** folder, then make sure the resource name matches the folder name.", inline=False)
        embed.add_field(name="How to Start It", value="Start the vehicle through **txAdmin** by using `ensure foldername` in your server config or by starting the resource from the txAdmin console.", inline=False)
        embed.add_field(name="Need Help?", value="If you need help installing the vehicle or have any questions, please open a **support ticket**.", inline=False)
        return embed

    def build_games_embed(self):
        embed = discord.Embed(
            title="🎮 Game Commands",
            description="Fun commands available.",
            colour=0x5865F2,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Games", icon_url=LOGO_URL)

        embed.add_field(
            name="🎲 Luck & Random",
            value=(
                "`!coinflip`\n"
                "`!roll [sides]`\n"
                "`!number <min> <max>`\n"
                "`!fortune`\n"
                "`!mysterybox`"
            ),
            inline=True
        )
        embed.add_field(
            name="🧠 Questions & Choice",
            value=(
                "`!8ball <question>`\n"
                "`!choose option1 | option2`\n"
                "`!trivia`\n"
                "`!wyr`\n"
                "`!truth`\n"
                "`!dare`"
            ),
            inline=True
        )
        embed.add_field(
            name="⚔️ Challenge",
            value=(
                "`!rps <choice>`\n"
                "`!guess <1-10>`\n"
                "`!scramble`\n"
                "`!battle @user`\n"
                "`!race @user`"
            ),
            inline=True
        )
        embed.add_field(
            name="🎰 Casino",
            value="Use the **Casino** help page for casino games and cash commands.",
            inline=False
        )
        embed.add_field(
            name="🎭 Fun Generators",
            value=(
                "`!compliment [@user]`\n"
                "`!rate <thing>`\n"
                "`!ship @user [@user]`\n"
                "`!achievement`\n"
                "`!namegen`"
            ),
            inline=True
        )
        embed.add_field(
            name="🎯 Random Pickers",
            value=(
                "`!emoji`\n"
                "`!colourpick`\n"
                "`!animalpick`\n"
                "`!foodpick`\n"
                "`!carpick`\n"
                "`!countrypick`\n"
                "`!superpower`"
            ),
            inline=True
        )
        embed.add_field(
            name="🤪 Silly / Misc",
            value=(
                "`!reverse <text>`\n"
                "`!say <text>`\n"
                "`!fact`\n"
                "`!memeidea`\n"
                "`!games`\n"
                "`!leaderboard`\n"
                "`!rank [@user]`"
            ),
            inline=True
        )
        return embed

    def build_utility_embed(self):
        embed = discord.Embed(
            title="🛠️ Utility Commands",
            description="Commands and general bot information.",
            colour=0x3498DB,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)

        embed.add_field(
            name="General Utility",
            value=(
                "`!payment` — Show payment methods\n"
                "`!botinfo` — Show bot purpose and features\n"
                "`!vehiclehelp` — Vehicle compatibility and install info\n"
                "`!ping` — Check bot latency\n"
                "`!rolereq` — Request an eligible role\n"
                "`!help` — Open this help menu"
            ),
            inline=False
        )
        embed.add_field(
            name="XP / Community",
            value=(
                "`!leaderboard` — View your game stats\n"
                "`!rank [@user]` — View rank information"
            ),
            inline=False
        )
        return embed

    def build_economy_embed(self):
        embed = discord.Embed(
            title="🎰 Casino Commands",
            description="Casino games and cash commands.",
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Casino", icon_url=LOGO_URL)

        embed.add_field(
            name="Casino / Betting",
            value=(
                "`!mines <bet> <mines>` / `!mine <bet> <mines>`\n"
                "`!bj <bet>` / `!blackjack <bet>`\n"
                "`!chess <bet>`\n"
                "`!plinko <bet>`\n"
                "`!roulette <bet> <red/black/green/number>`\n"
                "`!slots <bet>`\n"
                "`!crash <bet> [cashout]`\n"
                "`!rocket <bet>`\n"
                "`!dice <bet> <high/low>`\n"
                "`!baccarat <bet> <player/banker/tie>`"
            ),
            inline=False
        )
        embed.add_field(
            name="Cash / Progress",
            value=(
                "`!balance [@user]` / `!bal [@user]`\n"
                "`!beg`\n"
                "`!work`\n"
                "`!give @user <amount>`\n"
                "`!rewards`\n"
                "`!profit`\n"
                "`!mystats`"
            ),
            inline=False
        )
        embed.add_field(
            name="Casino Notes",
            value=(
                f"`!mines`, `!bj`, `!chess`, `!plinko`, `!roulette`, `!slots`, `!crash`, `!rocket`, `!dice`, and `!baccarat` have a **{BETTING_COOLDOWN_SECONDS} second** cooldown.\n"
                "You can only run **one active casino game at a time**."
            ),
            inline=False
        )
        return embed

    def build_rewards_embed(self):
        embed = discord.Embed(
            title="🎁 Rewards",
            description="Everything related to casino rewards and unlocks.",
            colour=0x2ECC71,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Rewards", icon_url=LOGO_URL)

        embed.add_field(
            name="🎰 How to Progress",
            value=(
                "Play casino commands to build up your cash:\n"
                "`!mines <bet> <mines>` / `!mine <bet> <mines>`\n"
                "`!bj <bet>` / `!blackjack <bet>`\n"
                "`!chess <bet>`\n"
                "`!plinko <bet>`\n"
                "`!roulette <bet> <red/black/green/number>`\n"
                "`!slots <bet>`\n"
                "`!crash <bet> [cashout]`\n"
                "`!rocket <bet>`\n"
                "`!dice <bet> <high/low>`\n"
                "`!baccarat <bet> <player/banker/tie>`\n"
                "`!beg`\n"
                "`!work`\n"
                "`!profit`\n"
                "`!mystats`"
            ),
            inline=False
        )

        role = discord.utils.get(self.member.guild.roles, id=CASINO_CAR_PACK_ROLE_ID)
        role_mention = role.mention if role else "Casino Car Pack"

        embed.add_field(
            name="🏆 Main Reward",
            value=(
                f"**{format_cash(CASINO_CAR_PACK_THRESHOLD)} cash** unlocks the **Casino Car Pack**.\n"
                "When you reach the requirement, the bot will automatically give you the role:\n"
                f"{role_mention}"
            ),
            inline=False
        )
        embed.add_field(
            name="🔥 Streak Bonuses",
            value=(
                f"`!beg` gives **+{format_cash(BEG_STREAK_BONUS)} 💵** extra per streak level after the first.\n"
                f"`!work` gives **+{format_cash(WORK_STREAK_BONUS)} 💵** extra per streak level after the first.\n"
                f"Streaks reset after **{STREAK_RESET_HOURS} hours** without claiming."
            ),
            inline=False
        )
        embed.add_field(
            name="🚗 What You Get",
            value="The Casino Car Pack contains **5 cars**.",
            inline=False
        )
        return embed

    def build_security_embed(self):
        embed = discord.Embed(
            title="🔐 Security Commands",
            description="Visible only to Security Team or Infrastructure staff.",
            colour=0xE67E22,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Security", icon_url=LOGO_URL)

        embed.add_field(
            name="Role Moderation",
            value=(
                "`!roleadd @user role name`\n"
                "`!roleremove @user role name`\n"
                "`!temprole @user role name [duration]`\n"
                "`!allroles @user`"
            ),
            inline=False
        )
        embed.add_field(
            name="Blacklist",
            value=(
                "`!blacklist @user [reason]`\n"
                "`!unblacklist @user`"
            ),
            inline=False
        )
        embed.add_field(
            name="Member Moderation",
            value=(
                "`!warn @user [reason]`\n"
                "`!warnings @user`\n"
                "`!clearwarns @user`\n"
                "`!note @user note text`\n"
                "`!notes @user`\n"
                "`!clearnotes @user`\n"
                "`!kick @user [reason]`\n"
                "`!ban @user [reason]`\n"
                "`!unban user_id [reason]`\n"
                "`!timeout @user 10m [reason]`\n"
                "`!untimeout @user [reason]`\n"
                "`!mute @user [reason]`\n"
                "`!unmute @user [reason]`\n"
                "`!nickname @user new nickname`"
            ),
            inline=False
        )
        embed.add_field(
            name="Channel / Message Moderation",
            value=(
                "`!lock [#channel]`\n"
                "`!unlock [#channel]`\n"
                "`!slowmode seconds [#channel]`\n"
                "`!purge amount`\n"
                "`!clean amount`\n"
                "`!history @user`"
            ),
            inline=False
        )
        embed.add_field(
            name="Advanced Moderation",
            value=(
                "`!rolestrip @user [reason]`\n"
                "`!rolestrip restore @user`\n"
                "`!gban @user [reason]`\n"
                "`!ungban user_id`"
            ),
            inline=False
        )
        return embed

    def build_infra_embed(self):
        embed = discord.Embed(
            title="🏗️ Infrastructure Commands",
            description="Visible only to Infrastructure staff.",
            colour=0xC0392B,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs Infrastructure", icon_url=LOGO_URL)

        embed.add_field(
            name="Server Lockdown",
            value=(
                "`!lockdown`\n"
                "`!unlockdown`"
            ),
            inline=False
        )
        embed.add_field(
            name="Casino Control",
            value="`!admincash @user amount`\n`!removecash @user amount`\n`!globaladdcash amount`\n`!globalresetcash`",
            inline=False
        )
        embed.add_field(
            name="Moderation System Control",
            value=(
                "`!auditlog`\n"
                "`!case case_id`\n"
                "`!editcase case_id new reason`"
            ),
            inline=False
        )
        return embed

    @discord.ui.button(label="Home", style=discord.ButtonStyle.primary, row=0)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "home"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Vehicle Support", style=discord.ButtonStyle.secondary, row=0)
    async def vehicle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "vehicle"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Games", style=discord.ButtonStyle.secondary, row=0)
    async def games_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "games"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Utility", style=discord.ButtonStyle.secondary, row=0)
    async def utility_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "utility"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Casino", style=discord.ButtonStyle.secondary, row=0)
    async def economy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "economy"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Rewards", style=discord.ButtonStyle.secondary, row=1)
    async def rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_page = "rewards"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Security", style=discord.ButtonStyle.danger, row=1)
    async def security_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_security_or_infrastructure_permission(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to view Security commands.",
                ephemeral=True
            )
            return
        self.active_page = "security"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

    @discord.ui.button(label="Infrastructure", style=discord.ButtonStyle.danger, row=1)
    async def infrastructure_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_infrastructure_permission(interaction.user):
            await interaction.response.send_message(
                "❌ You do not have permission to view Infrastructure commands.",
                ephemeral=True
            )
            return
        self.active_page = "infrastructure"
        self._apply_button_styles()
        await self._refresh_without_edit(interaction)

@bot.command(name="help")
async def help_command(ctx):
    view = AdvancedHelpView(ctx.author)
    message = await ctx.send(embed=view.build_home_embed(), view=view)
    view.message = message

# =========================================================
# ERROR HANDLER
# =========================================================
@bot.event
async def on_command_error(ctx, error):
    if getattr(ctx, "_typing_cm", None) is not None:
        try:
            await ctx._typing_cm.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            ctx._typing_cm = None

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MemberNotFound):
        embed = build_case_embed("GL Customs", "❌ User not found.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.MissingRequiredArgument):
        embed = build_case_embed("GL Customs", "❌ Missing required argument.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    embed = build_case_embed("GL Customs", f"❌ Error: `{error}`", 0xE74C3C)
    await ctx.send(embed=embed)

class RocketCashoutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cash Out", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.author.id:
            await interaction.response.send_message("❌ This is not your rocket game.", ephemeral=True)
            return

        if view.finished:
            await interaction.response.send_message("❌ This rocket game has already ended.", ephemeral=True)
            return

        view.cashed_out = True
        payout = int(round(view.bet_amount * view.current_multiplier))
        new_balance = add_user_balance(view.author.id, payout)
        record_house_profit("rocket", view.bet_amount, payout, view.author.id)
        await check_casino_car_pack_role(view.author, view.ctx)

        embed = view.build_embed(
            title="Rocket - Cashed Out",
            description=(
                f"🚀 You cashed out at **{view.current_multiplier:.2f}x**\n"
                f"└ Won: **{format_casino_result_display(payout, new_balance, view.display_bet_amount)} 💵**\n"
                f"└ Balance: **{format_cash(new_balance)} 💵**"
            ),
            colour=0x57F287
        )
        view.stop_game()
        await interaction.response.edit_message(embed=embed, view=view)


class RocketView(discord.ui.View):
    def __init__(self, author, bet_amount, ctx, display_bet_amount=None):
        super().__init__(timeout=45)
        self.author = author
        self.bet_amount = bet_amount
        self.ctx = ctx
        self.display_bet_amount = display_bet_amount
        self.current_multiplier = 1.00
        self.crash_point = generate_crash_point()
        self.finished = False
        self.cashed_out = False
        self.message = None
        self.add_item(RocketCashoutButton())

    def build_graph(self):
        points = max(1, min(20, int((self.current_multiplier - 1.0) * 4)))
        return "🟠" * points + "🚀"

    def build_embed(self, title=None, description=None, colour=0x5865F2):
        embed = discord.Embed(
            title=title or f"Rocket - {format_casino_bet_display(display_bet_amount=self.display_bet_amount)} 💵",
            description=description or (
                f"**{self.current_multiplier:.2f}x** Current Payout\n\n"
                f"{self.build_graph()}\n\n"
                f"Press **Cash Out** before the rocket crashes."
            ),
            colour=colour,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        return embed

    def stop_game(self):
        self.finished = True
        for child in self.children:
            child.disabled = True
        ACTIVE_GAME_USERS.discard(self.author.id)

    async def run_game(self):
        while not self.finished:
            await asyncio.sleep(0.85 if self.current_multiplier < 2 else 0.65 if self.current_multiplier < 5 else 0.5)
            self.current_multiplier = round(self.current_multiplier + (0.12 if self.current_multiplier < 2 else 0.22 if self.current_multiplier < 5 else 0.38), 2)

            if self.current_multiplier >= self.crash_point:
                self.finished = True
                record_house_profit("rocket", self.bet_amount, 0, self.author.id)
                self.stop_game()
                embed = self.build_embed(
                    title="Rocket - Crashed",
                    description=(
                        f"💥 The rocket crashed at **{self.crash_point:.2f}x**\n"
                        f"└ Lost: **{format_casino_result_display(self.bet_amount, get_user_balance(self.author.id), self.display_bet_amount)} 💵**\n"
                        f"└ Balance: **{format_cash(get_user_balance(self.author.id))} 💵**"
                    ),
                    colour=0xE74C3C
                )
                if self.message:
                    await self.message.edit(embed=embed, view=self)
                return

            if self.message and not self.cashed_out:
                embed = self.build_embed()
                await self.message.edit(embed=embed, view=self)

    async def on_timeout(self):
        if not self.finished:
            self.stop_game()
            embed = self.build_embed(
                title="Rocket - Timed Out",
                description=(
                    f"⏱️ The rocket game timed out.\n"
                    f"└ Lost: **{format_casino_result_display(self.bet_amount, get_user_balance(self.author.id), self.display_bet_amount)} 💵**\n"
                    f"└ Balance: **{format_cash(get_user_balance(self.author.id))} 💵**"
                ),
                colour=0xE67E22
            )
            if self.message:
                await self.message.edit(embed=embed, view=self)


@bot.command(name="rocket")
async def rocket(ctx, bet_amount=None):
    if not has_regular_member_permission(ctx.author):
        await ctx.send(embed=casino_denied_embed("Rocket"))
        return

    if ctx.author.id in ACTIVE_GAME_USERS:
        embed = discord.Embed(
            title="Rocket",
            description="❌ You already have an active game running.",
            colour=0xE74C3C,
            timestamp=now_dt()
        )
        embed.set_author(name="GL Customs", icon_url=LOGO_URL)
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    if bet_amount is None:
        embed = discord.Embed(
            title="Command: !rocket",
            description=(
                "**Description:** Launch the rocket and cash out before it crashes\n"
                "**Cooldown:** 3 seconds\n"
                "**Usage:**\n"
                "!rocket [bet]\n"
                "**Example:**\n"
                "!rocket 500k"
            ),
            colour=0xF1C40F,
            timestamp=now_dt()
        )
        embed.set_footer(text="GL Customs", icon_url=LOGO_URL)
        await ctx.send(embed=embed)
        return

    raw_bet_amount = bet_amount
    try:
        display_bet_amount = resolve_game_bet_display_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        display_bet_amount = None
    try:
        bet_amount = resolve_game_bet_amount(ctx.author.id, raw_bet_amount)
    except Exception:
        bet_amount = None

    if bet_amount is None:
        embed = build_case_embed("Rocket", "❌ Invalid bet. Use values like `100000`, `100k`, `5m`, `1b`, or `all`.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if bet_amount <= 0:
        embed = build_case_embed("Rocket", "❌ Bet amount must be above 0.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    current_balance = get_user_balance(ctx.author.id)
    if current_balance < bet_amount:
        embed = build_case_embed("Rocket", f"❌ You only have **{format_cash(current_balance)} 💵**.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    ok, _ = remove_user_balance(ctx.author.id, bet_amount)
    if not ok:
        embed = build_case_embed("Rocket", "❌ Could not remove bet from your balance.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    ACTIVE_GAME_USERS.add(ctx.author.id)
    view = RocketView(ctx.author, bet_amount, ctx, display_bet_amount=display_bet_amount)
    message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message
    asyncio.create_task(view.run_game())

# =========================================================
# RUN
# =========================================================
if not BOT_TOKEN:
    raise ValueError("TOKEN is missing from Railway Variables")

bot.run(BOT_TOKEN)
