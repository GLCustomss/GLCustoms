import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
import random
import io
from datetime import datetime, timedelta, timezone

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = ""

MODLOG_CHANNEL_ID = 1480303268981641256
LOGO_URL = "https://cdn.discordapp.com/attachments/1480303268981641256/1480574604983402517/GL_Customslogo.png"

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "gl_customs_data.json")

GAME_COMMAND_NAMES = {
    "coinflip", "roll", "eightball", "choose", "rps", "guess", "number",
    "slots", "rate", "ship", "trivia", "fortune", "compliment", "wyr",
    "truth", "dare", "emoji", "colourpick", "animalpick", "foodpick",
    "carpick", "countrypick", "superpower", "mysterybox", "race", "battle",
    "reverse", "say", "fact", "memeidea", "scramble", "achievement", "namegen"
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
        "leaderboard": {}
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
        [ctx.message, prompt_message],
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
    return any(role.id == INFRASTRUCTURE_ROLE_ID for role in member.roles)


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
    target = role_name.strip().lower()
    for role in guild.roles:
        if role.name.lower() == target:
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
    colour=0x2ECC71,
    case_id=None,
    decision_text=None,
):
    embed = discord.Embed(
        title="Role Requested",
        description=decision_text or f"A role has been requested by {requester.mention}.",
        colour=colour,
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
    embed.set_footer(text="GL Customs Games", icon_url=LOGO_URL)
    return embed


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
        await send_modlog(embed)

# =========================================================
# BASIC
# =========================================================
@bot.command()
async def ping(ctx):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Ping", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

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

    stats = get_user_game_stats(ctx.author.id)
    level_info = calculate_level_info(stats.get("xp", 0))
    rank = get_leaderboard_rank(ctx.author.id)
    top_entries = get_top_leaderboard(limit=5)

    top_lines = []
    for index, (user_id, entry) in enumerate(top_entries, start=1):
        member = ctx.guild.get_member(int(user_id))
        display_name = member.display_name if member else f"User {user_id}"
        top_lines.append(
            f"**{index}.** {display_name} — Level **{calculate_level_info(entry.get('xp', 0))['level']}** • **{entry.get('xp', 0)} XP**"
        )

    most_played = stats.get("command_counts", {})
    favourite_game = "None"
    if most_played:
        favourite_game = max(most_played.items(), key=lambda item: item[1])[0]

    embed = build_case_embed(
        "Game Leaderboard",
        "Here are your current game stats.",
        0x5865F2,
        user=ctx.author,
        extra_fields=[
            ("Rank", f"#{rank}" if rank else "Unranked", True),
            ("Level", str(level_info["level"]), True),
            ("Total XP", str(level_info["xp"]), True),
            ("Games Played", str(stats.get("games_played", 0)), True),
            ("Favourite Game", favourite_game, True),
            ("Next Level In", f"{level_info['xp_needed_for_next']} XP", True),
            ("Top Players", "\n".join(top_lines) if top_lines else "No leaderboard data yet.", False)
        ]
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
    "When the build starts at £500 and ends at £5,000.",
    "POV: you said 'just one more mod'.",
    "That feeling when the part arrives and it is the wrong one.",
    "When the car sounds faster than it actually is.",
    "Trying to save money but buying another upgrade anyway.",
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
            "`!slots`",
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

    embed = game_embed(
        "🎱 Magic 8 Ball",
        f"**Question:** {question}\n\n**Answer:** {random.choice(EIGHTBALL_RESPONSES)}"
    )
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
async def slots(ctx):
    if not has_regular_member_permission(ctx.author):
        embed = game_embed("Slots", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣", "🚗"]
    spin = [random.choice(symbols) for _ in range(3)]
    if len(set(spin)) == 1:
        result = random.choice([
            "🎉 **JACKPOT!** Everything lined up perfectly. That was a huge spin.",
            "🎉 **JACKPOT!** The machine fully paid out for you there.",
            "🎉 **JACKPOT!** Massive hit. You cleared the reels."
        ])
        colour = 0x2ECC71
    elif len(set(spin)) == 2:
        result = random.choice([
            "✨ Nice result. You landed a pair and came close to the full hit.",
            "✨ Solid spin. A pair is still a decent return.",
            "✨ Not the jackpot, but definitely not bad."
        ])
        colour = 0xF1C40F
    else:
        result = random.choice([
            "❌ No win this time. The machine was not feeling generous.",
            "❌ The reels did you no favours there.",
            "❌ Rough spin. Nothing lined up."
        ])
        colour = 0xE67E22

    embed = game_embed("🎰 Slots", " | ".join(spin) + f"\n\n{result}", colour)
    await ctx.send(embed=embed)


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
# ROLESTRIP
# =========================================================
@bot.command(name="rolestrip")
async def rolestrip(ctx, *args):
    if not has_rolestrip_permission(ctx.author):
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
            if role.position >= author_highest:
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
        if role.position >= author_highest:
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
    if not has_security_or_infrastructure_permission(ctx.author):
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
    if not has_security_or_infrastructure_permission(ctx.author):
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
@bot.command(name="roleadd")
async def roleadd(ctx, member: discord.Member = None, *, role_name=None):
    if not has_role_command_permission(ctx.author):
        embed = build_case_embed("Give Role", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None or role_name is None:
        embed = build_case_embed("Give Role", "❌ Usage: `!roleadd @user role name`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    role = role_lookup_case_insensitive(ctx.guild, role_name)
    if not role:
        embed = build_case_embed("Give Role", "❌ Role not found.", 0xE74C3C, user=member)
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
async def ban(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_security_or_infrastructure_permission(ctx.author):
        embed = build_case_embed("Ban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Ban", "❌ Usage: `!ban @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Ban", "This is a dangerous action.")
    if not confirmed:
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Ban", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    try:
        await member.ban(reason=f"Ban by {ctx.author} | {reason}")
    except discord.Forbidden:
        embed = build_case_embed("Ban", "❌ I do not have permission to ban that user.", 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("ban_case")
    record_case(case_id, "BAN", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Ban",
        "The user has been banned from this server.",
        0xC0392B,
        case_id=case_id,
        user=member,
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
            extra_fields=[("User ID", str(user_id), True)]
        )
        await ctx.send(embed=embed)
        return

    user_obj = discord.Object(id=user_id)

    try:
        await ctx.guild.unban(user_obj, reason=f"Unban by {ctx.author} | {reason}")
    except discord.NotFound:
        embed = build_case_embed("Unban", "❌ That user is not banned here.", 0xE74C3C)
        await ctx.send(embed=embed)
        return
    except discord.Forbidden:
        embed = build_case_embed("Unban", "❌ I do not have permission to unban that user.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("unban_case")
    record_case(case_id, "UNBAN", user_id, ctx.author.id, reason)

    embed = build_case_embed(
        "Unban",
        "The user has been unbanned from this server.",
        0x2ECC71,
        case_id=case_id,
        reason=reason,
        extra_fields=[("User ID", str(user_id), True)]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="gban")
async def gban(ctx, member: discord.Member = None, *, reason="No reason provided"):
    if not has_infrastructure_permission(ctx.author):
        embed = build_case_embed("Global Ban", "❌ You do not have permission to use this command.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    if member is None:
        embed = build_case_embed("Global Ban", "❌ Usage: `!gban @user [reason]`", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    confirmed = await confirm_action(ctx, "Global Ban", "This is a dangerous action.")
    if not confirmed:
        return

    ok, msg = can_moderate(ctx.author, member)
    if not ok:
        embed = build_case_embed("Global Ban", msg, 0xE74C3C, user=member)
        await ctx.send(embed=embed)
        return

    add_global_ban(member.id, ctx.author.id, reason)
    success_guilds = []
    failed_guilds = []

    for guild in bot.guilds:
        try:
            await guild.ban(discord.Object(id=member.id), reason=f"GBAN by {ctx.author} | {reason}")
            success_guilds.append(guild.name)
        except (discord.Forbidden, discord.HTTPException):
            failed_guilds.append(guild.name)

    case_id = next_case_id("gban_case")
    record_case(case_id, "GBAN", member.id, ctx.author.id, reason)

    embed = build_case_embed(
        "Global Ban",
        "The user has been globally banned from GL Customs and connected servers.",
        0xC0392B,
        case_id=case_id,
        user=member,
        reason=reason,
        extra_fields=[
            ("Guilds Banned In", "\n".join(success_guilds) if success_guilds else "None", False),
            ("Guilds Failed", "\n".join(failed_guilds) if failed_guilds else "None", False),
        ]
    )
    await ctx.send(embed=embed)
    await send_modlog(embed)


@bot.command(name="ungban")
async def ungban(ctx, user_id: int = None):
    if ctx.author.id not in UNBAN_GBAN_BYPASS_USER_IDS and ctx.author.id != ctx.guild.owner_id:
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
        embed = build_case_embed("Un-Global Ban", "❌ No global ban entry found for that user ID.", 0xE74C3C)
        await ctx.send(embed=embed)
        return

    case_id = next_case_id("ungban_case")
    record_case(case_id, "UNGBAN", user_id, ctx.author.id, "Global ban removed")

    embed = build_case_embed(
        "Un-Global Ban",
        "The global ban has been removed.",
        0x2ECC71,
        case_id=case_id,
        extra_fields=[
            ("User ID", str(user_id), True),
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
        case_id=case_id,
        extra_fields=[("Channel", channel.mention, True)]
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
        case_id=case_id,
        extra_fields=[("Channel", channel.mention, True)]
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
# ADVANCED HELP MENU
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
            ("Available Roles", "\n".join(role.name for role in page_roles) if page_roles else "No roles available.", False),
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
        if hasattr(self, "home_button"):
            self.home_button.style = discord.ButtonStyle.secondary
        if hasattr(self, "games_button"):
            self.games_button.style = discord.ButtonStyle.secondary
        if hasattr(self, "utility_button"):
            self.utility_button.style = discord.ButtonStyle.secondary
        if hasattr(self, "security_button"):
            self.security_button.style = discord.ButtonStyle.secondary
        if hasattr(self, "infrastructure_button"):
            self.infrastructure_button.style = discord.ButtonStyle.secondary

        if self.active_page == "home" and hasattr(self, "home_button"):
            self.home_button.style = discord.ButtonStyle.primary
        elif self.active_page == "games" and hasattr(self, "games_button"):
            self.games_button.style = discord.ButtonStyle.primary
        elif self.active_page == "utility" and hasattr(self, "utility_button"):
            self.utility_button.style = discord.ButtonStyle.primary
        elif self.active_page == "security" and hasattr(self, "security_button"):
            self.security_button.style = discord.ButtonStyle.danger
        elif self.active_page == "infrastructure" and hasattr(self, "infrastructure_button"):
            self.infrastructure_button.style = discord.ButtonStyle.danger

    def _get_current_embed(self):
        if self.active_page == "home":
            return self.build_home_embed()
        if self.active_page == "games":
            return self.build_games_embed()
        if self.active_page == "utility":
            return self.build_utility_embed()
        if self.active_page == "security":
            return self.build_security_embed()
        if self.active_page == "infrastructure":
            return self.build_infra_embed()
        return self.build_home_embed()

    async def _refresh_without_edit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        new_view = AdvancedHelpView(interaction.user, active_page=self.active_page)
        new_message = await interaction.channel.send(
            embed=new_view._get_current_embed(),
            view=new_view
        )
        new_view.message = new_message

        try:
            await interaction.message.delete()
        except Exception:
            pass

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
                "`!slots`\n"
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
            name="Role System Control",
            value=(
                "`!rolestrip @user [reason]`\n"
                "`!rolestrip restore @user`"
            ),
            inline=False
        )
        embed.add_field(
            name="Global Moderation",
            value=(
                "`!gban @user [reason]`\n"
                "`!ungban user_id`"
            ),
            inline=False
        )
        embed.add_field(
            name="Server Lockdown",
            value=(
                "`!lockdown`\n"
                "`!unlockdown`"
            ),
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

# =========================================================
# RUN
# =========================================================
bot.run(BOT_TOKEN)