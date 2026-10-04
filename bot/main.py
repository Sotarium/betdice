"""
Betdice Discord bot
Requires env: DISCORD_TOKEN
Optional: SITE_URL
"""
import os
import random
import math
import discord
from discord import app_commands
import sqlite3
import time
import io
import asyncio
from aiohttp import web
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, required for bots
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

SITE_URL = os.getenv(
    "SITE_URL",
    "https://betdice-frouxzys-projects-fcc3f71b.vercel.app",
)
BOT_INTERNAL_SECRET = os.getenv("BOT_INTERNAL_SECRET", "betdice_secret")
BOT_PORT = int(os.getenv("PORT", os.getenv("BOT_PORT", "8080")))

LAYOUT = {
    "important": [
        ("ðŸŽ«ãƒ»ticket", False),
        ("ðŸ“¢ãƒ»news", True),
        ("ðŸ“©ãƒ»invite-rewards", False),
        ("ðŸ”¨ãƒ»event", False),
        ("ðŸ’ãƒ»giveaway", False),
        ("ðŸš€-invite", False),
    ],
    "ðŸŽ²ãƒ»PLAY": [
        ("ðŸ’°-history", True),
        ("ðŸ’¸ãƒ»play-1", False),
        ("ðŸ’¸ãƒ»play-2", False),
        ("ðŸ’¸ãƒ»play-3", False),
    ],
    "ðŸ’¬ãƒ»COMMUNITY": [
        ("âœ‰ï¸ãƒ»general", False),
        ("âœ…ãƒ»vouch", False),
    ],
}

ALLOWED = [
    "view_channel", "create_instant_invite", "send_messages",
    "attach_files", "read_message_history", "create_polls",
    "use_application_commands",
]
DENIED = [
    "manage_channels", "manage_permissions", "manage_webhooks",
    "send_messages_in_threads", "create_public_threads", "create_private_threads",
    "embed_links", "add_reactions",
    "use_external_emojis", "use_external_stickers", "mention_everyone",
    "manage_messages", "pin_messages", "bypass_slowmode", "manage_threads",
    "send_tts_messages", "send_voice_messages",
    "connect", "speak", "stream", "use_soundboard", "use_external_sounds",
    "use_voice_activation", "priority_speaker", "mute_members", "deafen_members",
    "move_members", "set_voice_channel_status",
    "use_embedded_activities", "use_external_apps",
    "create_events", "manage_events",
]


def everyone_overwrite(read_only: bool = False) -> discord.PermissionOverwrite:
    valid = discord.Permissions.VALID_FLAGS
    perms = {p: True for p in ALLOWED if p in valid}
    perms.update({p: False for p in DENIED if p in valid})
    if read_only:
        perms["send_messages"] = False
    return discord.PermissionOverwrite(**perms)


class SetupBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print(f"SITE_URL={SITE_URL}")
        await refund_orphaned_games()
        if not self.guilds:
            print("Bot is NOT in any server. Re-invite it with the OAuth2 URL.")
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Commands synced to: {guild.name}")
            try:
                await ensure_dice_emoji(guild)
            except Exception as e:
                print(f"Could not create dice emoji in {guild.name}: {e}")


bot = SetupBot()

ALLOWED_CATEGORY_ID = 1555621407256485918


async def category_check(interaction: discord.Interaction) -> bool:
    if getattr(interaction.channel, "category_id", None) == ALLOWED_CATEGORY_ID:
        return True
    await interaction.response.send_message(
        "You can't use this command here. Use it in the play channels.",
        ephemeral=True,
    )
    return False


bot.tree.interaction_check = category_check


DICE_IMAGE_URL = "https://i.imgur.com/jNKCFwO.png"
DICE_EMOJI_NAME = "dice"


async def ensure_dice_emoji(guild: discord.Guild):
    import aiohttp
    existing = discord.utils.get(guild.emojis, name=DICE_EMOJI_NAME)
    if existing:
        return existing
    async with aiohttp.ClientSession() as session:
        async with session.get(
            DICE_IMAGE_URL, headers={"User-Agent": "Mozilla/5.0"}
        ) as resp:
            data = await resp.read()
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((128, 128))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        data = buf.getvalue()
    except ImportError:
        pass
    return await guild.create_custom_emoji(name=DICE_EMOJI_NAME, image=data)


def dice_emoji(guild) -> str:
    emoji = discord.utils.get(guild.emojis, name=DICE_EMOJI_NAME) if guild else None
    return str(emoji) if emoji else "\U0001F3B2"


db = sqlite3.connect("dice.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    "id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, last_daily REAL DEFAULT 0, promo_balance REAL DEFAULT 0, wager_required REAL DEFAULT 0)"
)
try:
    db.execute("ALTER TABLE users ADD COLUMN promo_balance REAL DEFAULT 0")
    db.commit()
except sqlite3.OperationalError:
    pass

try:
    db.execute("ALTER TABLE users ADD COLUMN wager_required REAL DEFAULT 0")
    db.commit()
except sqlite3.OperationalError:
    pass

db.execute(
    "CREATE TABLE IF NOT EXISTS transactions ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, balance_after REAL, ts REAL)"
)
db.execute(
    "CREATE TABLE IF NOT EXISTS mines_clicks ("
    "user_id INTEGER, tile_index INTEGER, count INTEGER DEFAULT 0, "
    "PRIMARY KEY (user_id, tile_index))"
)
db.execute(
    "CREATE TABLE IF NOT EXISTS active_games ("
    "user_id INTEGER PRIMARY KEY, game TEXT, bet_amount REAL, started_at REAL)"
)
db.commit()


def start_active_game(user_id: int, game: str, bet_amount: float):
    """Record a game as in-progress so it can be refunded on bot restart."""
    db.execute(
        "INSERT OR REPLACE INTO active_games (user_id, game, bet_amount, started_at) VALUES (?, ?, ?, ?)",
        (user_id, game, bet_amount, time.time()),
    )
    db.commit()


def end_active_game(user_id: int):
    """Remove game from active tracking when it finishes normally."""
    db.execute("DELETE FROM active_games WHERE user_id = ?", (user_id,))
    db.commit()


async def refund_orphaned_games():
    """On bot startup: refund any games that were in-progress when bot died."""
    rows = db.execute("SELECT user_id, game, bet_amount FROM active_games").fetchall()
    if not rows:
        return
    print(f"[Startup] Refunding {len(rows)} orphaned game(s)...")
    for user_id, game, bet_amount in rows:
        add_balance(user_id, bet_amount, tx_type="refund")
        print(f"  Refunded {bet_amount} to user {user_id} ({game})")
        try:
            user = await bot.fetch_user(user_id)
            await user.send(
                f"Your **{game}** game was interrupted when the bot restarted.\n"
                f"Your bet of **{bet_amount:,.2f}** dices has been refunded."
            )
        except Exception:
            pass
    db.execute("DELETE FROM active_games")
    db.commit()
    print(f"[Startup] Refunds complete.")



def record_mines_click(user_id: int, tile_index: int):
    """Track which tile a player clicked (safe tiles only)."""
    db.execute(
        "INSERT INTO mines_clicks (user_id, tile_index, count) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, tile_index) DO UPDATE SET count = count + 1",
        (user_id, tile_index),
    )
    db.commit()


def get_biased_bomb_positions(user_id: int, total_tiles: int, bombs: int) -> set:
    """
    Bias bomb placement based on player click history.
    - If player has a pattern: bomb is 25% more likely in their top tiles.
    - If player clicks randomly: 50/50 split between two alternating zones.
    - If not enough history: pure random.
    """
    rows = db.execute(
        "SELECT tile_index, count FROM mines_clicks WHERE user_id = ? AND tile_index < ?",
        (user_id, total_tiles),
    ).fetchall()

    total_clicks = sum(r[1] for r in rows)

    if total_clicks < 10:
        # Not enough data — pure random
        return set(random.sample(range(total_tiles), bombs))

    # Build weight array
    uniform = 1.0 / total_tiles
    weights = [uniform] * total_tiles
    for tile_idx, count in rows:
        freq = count / total_clicks
        weights[tile_idx] = freq

    # Detect if player has a pattern (high variance) or is random (low variance)
    avg = sum(weights) / len(weights)
    variance = sum((w - avg) ** 2 for w in weights) / len(weights)
    random_threshold = (uniform ** 2) * 0.3  # low variance = random

    if variance <= random_threshold:
        # Random player — 50/50 between two alternating zones
        # Zone A: even tile indices (cols 0,2,4 per row)
        # Zone B: odd tile indices (cols 1,3 per row)
        zone = random.randint(0, 1)  # 0=even zone, 1=odd zone
        zone_tiles = [i for i in range(total_tiles) if i % 2 == zone]
        other_tiles = [i for i in range(total_tiles) if i % 2 != zone]
        # 60% weight on chosen zone tiles, 40% on others
        biased_weights = []
        for i in range(total_tiles):
            if i in zone_tiles:
                biased_weights.append(0.6 / len(zone_tiles))
            else:
                biased_weights.append(0.4 / len(other_tiles))
    else:
        # Pattern player — boost their top tiles by 25%
        biased_weights = []
        for w in weights:
            if w > uniform:
                biased_weights.append(w * 1.25)  # 25% boost on preferred tiles
            else:
                biased_weights.append(w)

    # Weighted sampling without replacement for bomb positions
    bomb_positions = set()
    available = list(range(total_tiles))
    avail_weights = list(biased_weights)
    for _ in range(bombs):
        total_w = sum(avail_weights)
        norm = [w / total_w for w in avail_weights]
        chosen = random.choices(available, weights=norm, k=1)[0]
        idx = available.index(chosen)
        bomb_positions.add(chosen)
        available.pop(idx)
        avail_weights.pop(idx)

    return bomb_positions



def log_tx(uid: int, tx_type: str, amount: float):
    """Record a transaction for profit tracking."""
    row = db.execute("SELECT balance, promo_balance FROM users WHERE id=?", (uid,)).fetchone()
    bal_after = (row[0] or 0.0) + (row[1] or 0.0) if row else 0.0
    db.execute(
        "INSERT INTO transactions (user_id, type, amount, balance_after, ts) VALUES (?, ?, ?, ?, ?)",
        (uid, tx_type, amount, bal_after, time.time()),
    )
    db.commit()


DAILY_AMOUNT = 100.0
DAILY_COOLDOWN = 24 * 60 * 60



def get_user(uid: int):
    row = db.execute("SELECT balance, last_daily, promo_balance, wager_required FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        db.execute("INSERT INTO users (id, balance, last_daily, promo_balance, wager_required) VALUES (?, 0, 0, 0, 0)", (uid,))
        db.commit()
        return 0.0, 0.0, 0.0, 0.0
    bal = row[0] or 0.0
    daily = row[1] or 0.0
    promo = row[2] if len(row) > 2 and row[2] is not None else 0.0
    wager_req = row[3] if len(row) > 3 and row[3] is not None else 0.0
    return bal, daily, promo, wager_req


def add_balance(uid: int, amount: float, is_promo: bool = False, add_wager: float = 0.0, tx_type: str = None):
    """
    - is_promo=True: locked balance that cannot be withdrawn/tipped.
    - add_wager: adds wagering requirement before any withdrawals are allowed.
    - amount < 0 (bets): reduces remaining wager requirement!
    - tx_type: optional transaction tag ('deposit', 'withdraw', 'bet', etc.)
    """
    get_user(uid)
    if add_wager > 0:
        db.execute("UPDATE users SET wager_required = wager_required + ? WHERE id=?", (add_wager, uid))

    if is_promo and amount > 0:
        db.execute("UPDATE users SET promo_balance = promo_balance + ? WHERE id=?", (amount, uid))
    elif amount < 0:
        # User is placing a bet: deduct from promo_balance first, then real balance
        deduct = -amount
        bal, _, promo, wager_req = get_user(uid)

        # Progress wagering requirement
        if wager_req > 0:
            new_wager = max(0.0, wager_req - deduct)
            db.execute("UPDATE users SET wager_required = ? WHERE id=?", (new_wager, uid))

        from_promo = min(promo, deduct)
        from_real = deduct - from_promo
        if from_promo > 0:
            db.execute("UPDATE users SET promo_balance = promo_balance - ? WHERE id=?", (from_promo, uid))
        if from_real > 0:
            db.execute("UPDATE users SET balance = balance - ? WHERE id=?", (from_real, uid))
    else:
        # Standard positive clean balance (deposit or game winnings)
        db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    db.commit()

    if tx_type is None:
        tx_type = "bet" if amount < 0 else ("promo" if is_promo else "balance")
    log_tx(uid, tx_type, amount)


def get_withdrawable_balance(uid: int) -> float:
    row = get_user(uid)
    wager_req = row[3]
    if wager_req > 0:
        return 0.0  # Must complete wager requirement first
    return row[0]


def get_total_balance(uid: int) -> float:
    row = get_user(uid)
    return row[0] + row[2]


async def notify_user_deposit(discord_id: int, amount: float, new_balance: float):
    try:
        user = await bot.fetch_user(discord_id)
        if user:
            embed = discord.Embed(
                title="Deposit Credited!",
                description=(
                    f"Your deposit of **+{amount:,.2f}** has been confirmed!\n"
                    f"Your new balance is **{new_balance:,.2f}** dices."
                ),
                color=0x0498fb,
            )
            await user.send(embed=embed)
    except Exception as e:
        print(f"[Notify Error] Could not DM user {discord_id}: {e}")


async def sync_website_deposit(discord_id: int, amount: float, new_balance: float):
    try:
        import aiohttp
        user = await bot.fetch_user(discord_id)
        username = user.name if user else f"User-{discord_id}"
        avatar_hash = user.avatar.key if user and user.avatar else None

        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{SITE_URL}/api/users/sync",
                json={
                    "discordId": str(discord_id),
                    "username": username,
                    "avatar": avatar_hash,
                    "type": "Deposit",
                    "amount": amount,
                    "balance": new_balance,
                    "profit": 0,
                    "label": "crypto_deposit",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        print(f"[Sync Error] Website sync failed: {e}")


async def handle_deposit_credit(request: web.Request):
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {BOT_INTERNAL_SECRET}"
    if auth_header != expected:
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        discord_id = int(data.get("discordId"))
        amount = float(data.get("amount", 0))

        if amount <= 0:
            return web.json_response({"error": "invalid amount"}, status=400)

        add_balance(discord_id, amount, tx_type="deposit")
        new_balance, _, _, _ = get_user(discord_id)
        print(f"[Deposit Webhook] Credited user {discord_id} with {amount}. New Balance: {new_balance}")

        asyncio.create_task(notify_user_deposit(discord_id, amount, new_balance))
        asyncio.create_task(sync_website_deposit(discord_id, amount, new_balance))

        return web.json_response({
            "status": "credited",
            "discordId": str(discord_id),
            "amount": amount,
            "newBalance": new_balance,
        })
    except Exception as e:
        print(f"[Deposit Webhook Error] {e}")
        return web.json_response({"error": str(e)}, status=500)


async def start_http_server():
    app = web.Application()
    app.router.add_post("/deposit-credit", handle_deposit_credit)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", BOT_PORT)
    await site.start()
    print(f"[Bot Webhook] HTTP listener running on port {BOT_PORT}")


async def get_deposit_address(discord_id: int, username: str, avatar_hash, currency: str = None):
    import aiohttp
    payload = {"discordId": str(discord_id)}
    if currency:
        payload["currency"] = currency.upper()
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SITE_URL}/api/plisio/deposit",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            text = await r.text()
            status = r.status
            try:
                data = await r.json(content_type=None)
            except Exception:
                data = {"error": text[:300]}

        return status, data


class WithdrawModal(discord.ui.Modal, title="Withdraw"):
    amount = discord.ui.TextInput(
        label="Amount (dices)",
        placeholder="e.g. 50",
        required=True,
        min_length=1,
        max_length=12,
    )
    address = discord.ui.TextInput(
        label="Your wallet address (SOL or LTC)",
        placeholder="Paste SOL or LTC address",
        required=True,
        min_length=10,
        max_length=128,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = float(self.amount.value.replace(",", "."))
            if amt <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Invalid amount.", ephemeral=True)
            return

        bal, _, promo, wager_req = get_user(interaction.user.id)
        if wager_req > 0:
            await interaction.response.send_message(
                f"Withdrawal locked: You have **{wager_req:,.2f}** dices remaining in wagering requirements.\nPlay games to complete your wager requirement before withdrawing!",
                ephemeral=True,
            )
            return

        withdrawable = get_withdrawable_balance(interaction.user.id)
        if amt > withdrawable:
            msg = f"Not enough withdrawable balance. You have **{withdrawable:,.2f}** withdrawable dices."
            if promo > 0:
                msg += f"\n*(You have **{promo:,.2f}** in promo/non-withdrawable bonus that cannot be withdrawn directly. Play games to turn them into real winnings!)*"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        target_addr = self.address.value.strip()
        # Detect currency
        # SOL addresses are base58 and typically 32-44 characters, LTC starts with L, M, or ltc1
        currency = "LTC" if (target_addr.startswith("L") or target_addr.startswith("M") or target_addr.startswith("ltc1")) else "SOL"

        # Deduct balance upfront
        add_balance(interaction.user.id, -amt, tx_type="withdraw")

        import aiohttp
        payout_success = False
        payout_error = None
        txn_id = None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{SITE_URL}/api/plisio/withdraw",
                    json={
                        "secret": BOT_INTERNAL_SECRET,
                        "currency": currency,
                        "to": target_addr,
                        "amount": amt,
                    },
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as resp:
                    resp_data = await resp.json(content_type=None)
                    if resp.status == 200 and resp_data.get("status") == "success":
                        payout_success = True
                        txn_id = resp_data.get("txn_id")
                    else:
                        payout_error = resp_data.get("error", "Plisio withdrawal failed")
        except Exception as e:
            payout_error = str(e)

        if not payout_success:
            # Refund balance to user
            add_balance(interaction.user.id, amt, tx_type="refund")
            await interaction.followup.send(
                f"âŒ **Withdrawal Failed:** {payout_error}\nYour balance of **{amt:,.2f}** dices has been refunded.",
                ephemeral=True,
            )
            return

        avatar_hash = interaction.user.avatar.key if interaction.user.avatar else None
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{SITE_URL}/api/users/sync",
                    json={
                        "discordId": str(interaction.user.id),
                        "username": interaction.user.name,
                        "avatar": avatar_hash,
                        "type": "Withdraw",
                        "amount": amt,
                        "balance": get_user(interaction.user.id)[0],
                        "profit": 0,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception as e:
            print(f"Site sync error: {e}")

        tx_info = f"\n**Transaction ID:** `{txn_id}`" if txn_id else ""
        embed = discord.Embed(
            title="âœ… Withdrawal Sent!",
            description=(
                f"**Amount:** {amt:,.2f} dices\n"
                f"**Currency:** {currency}\n"
                f"**Address:** `{target_addr}`{tx_info}\n\n"
                "The payout has been broadcast to the blockchain."
            ),
            color=0x0498fb,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def send_deposit_dm(user: discord.User, currency: str):
    """Fetch deposit address for one currency and DM it to the user."""
    try:
        status, data = await get_deposit_address(user.id, user.name,
                                                  user.avatar.key if user.avatar else None,
                                                  currency=currency)
    except Exception as e:
        await user.send(f"Network error fetching deposit address: `{e}`")
        return

    addresses = data.get("addresses") or []
    if not addresses and data.get("address"):
        addresses = [{"address": data["address"], "currency": data.get("currency", currency), "min_sum": 0}]

    if status != 200 or not addresses:
        err = data.get("error", str(data)[:200])
        await user.send(f"Could not get deposit address.\n`{err}`")
        return

    a = addresses[0]
    cur = (a.get("currency") or currency).upper()
    addr = a.get("address") or "?"
    min_s = a.get("min_sum") or 0
    cur_label = "Solana (SOL)" if cur == "SOL" else "Litecoin (LTC)" if cur == "LTC" else cur

    embed = discord.Embed(
        title="Deposit",
        description=(
            f"**{cur_label}**\n"
            f"```{addr}```\n"
            + (f"Min deposit: **${min_s:.2f}** USD\n\n" if min_s and min_s > 0 else "\n")
            + "Wrong network = lost funds."
        ),
        color=0x0498fb,
    )
    embed.set_footer(text="This is your permanent deposit address")
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        pass  # DMs disabled — caller handles this


class DepositCoinView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def _handle(self, interaction: discord.Interaction, currency: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your balance.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await send_deposit_dm(interaction.user, currency)
            await interaction.followup.send(
                f"Deposit address sent to your DMs.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Could not DM you. Please enable DMs from server members.", ephemeral=True
            )

    @discord.ui.button(label="Solana", style=discord.ButtonStyle.primary)
    async def sol(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "SOL")

    @discord.ui.button(label="Litecoin", style=discord.ButtonStyle.secondary)
    async def ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "LTC")


class BalanceView(discord.ui.View):
    def __init__(self, target_id: int):
        super().__init__(timeout=180)
        self.target_id = target_id

    @discord.ui.button(label="Deposit", style=discord.ButtonStyle.secondary)
    async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This is not your balance.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Deposit",
            description="Which network do you want to deposit with?",
            color=0x0498fb,
        )
        await interaction.response.send_message(
            embed=embed,
            view=DepositCoinView(interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.secondary)
    async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This is not your balance.", ephemeral=True)
            return
        await interaction.response.send_modal(WithdrawModal())


@bot.tree.command(name="bal", description="Show your dice balance")
@app_commands.describe(user="Check someone else's balance")
async def bal(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    bal, _, promo, wager_req = get_user(target.id)
    total = bal + promo
    title = "Your balance" if target == interaction.user else f"{target.display_name}'s balance"

    desc = f"{dice_emoji(interaction.guild)} **{total:,.2f}** dices"
    if promo > 0:
        desc += f"\n• Withdrawable: **{bal:,.2f}** dices\n• Non-withdrawable: **{promo:,.2f}** dices"
    if wager_req > 0:
        desc += f"\n• Wager Required: **{wager_req:,.2f}** dices"

    embed = discord.Embed(
        title=title,
        description=desc,
        color=0x0498fb,
    )

    if target == interaction.user:
        view = BalanceView(target.id)
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed)




# ========================================================
# MINES GAMEMODE
# ========================================================

def get_mines_multiplier(total_tiles: int, bombs: int, revealed: int) -> float:
    """
    Provably fair casino mines multiplier.
    For 5x5 with 1 bomb full clear, scales up to 24.0x.
    """
    if revealed == 0:
        return 1.0
    safe_tiles = total_tiles - bombs
    if safe_tiles <= 0:
        return 1.0
    # Standard probability-based multiplier with 5% house edge
    prob = math.comb(safe_tiles, revealed) / math.comb(total_tiles, revealed)
    mult = 0.95 / prob
    return round(mult, 2)


class MinesButton(discord.ui.Button):
    def __init__(self, index: int, row: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=row)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return
        await view.handle_tile_click(interaction, self)


class MinesView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: float, bombs: int, grid_size: int = 5):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.bombs = bombs
        self.grid_size = 5
        # 20 tiles across rows 0-3 (5 per row), cashout alone in row 4
        self.total_tiles = 20
        self.safe_tiles = self.total_tiles - bombs
        self.revealed_indices = set()
        self.game_over = False

        # Biased bomb placement based on player click history
        self.bomb_positions = get_biased_bomb_positions(user_id, self.total_tiles, self.bombs)

        # Build 20 tiles across rows 0-3 (5 per row)
        for i in range(20):
            row = i // 5
            btn = MinesButton(index=i, row=row)
            self.add_item(btn)

        # Cashout button alone in row 4 (appears below the full grid)
        self.cashout_btn = discord.ui.Button(
            label="Cashout (0.00)",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=4,
        )
        self.cashout_btn.callback = self.handle_cashout
        self.add_item(self.cashout_btn)


    @property
    def current_multiplier(self) -> float:
        return get_mines_multiplier(self.total_tiles, self.bombs, len(self.revealed_indices))

    @property
    def current_payout(self) -> float:
        return round(self.bet_amount * self.current_multiplier, 2)

    def get_game_embed(self, status: str = "active", cashout_amt: float = 0.0) -> discord.Embed:
        revealed_count = len(self.revealed_indices)
        if status == "active":
            embed = discord.Embed(
                title="Mines",
                description=(
                    f"**Bet:** {self.bet_amount:,.2f} dices\n"
                    f"**Multiplier:** {self.current_multiplier:.2f}x\n"
                    f"**Payout:** +{self.current_payout:,.2f} dices"
                ),
                color=0x0498fb,
            )
        elif status == "win":
            embed = discord.Embed(
                title="Cashed Out",
                description=(
                    f"**{self.current_multiplier:.2f}x** — +{cashout_amt:,.2f} dices"
                ),
                color=0x0498fb,
            )
        elif status == "all_cleared":
            embed = discord.Embed(
                title="Board Cleared",
                description=(
                    f"**{self.current_multiplier:.2f}x** — +{cashout_amt:,.2f} dices"
                ),
                color=0x0498fb,
            )
        else:  # lost
            embed = discord.Embed(
                title="Bomb Hit",
                description=(
                    f"Lost **{self.bet_amount:,.2f}** dices · {revealed_count} tiles cleared"
                ),
                color=0x0498fb,
            )
        return embed


    async def handle_tile_click(self, interaction: discord.Interaction, button: MinesButton):
        if self.game_over:
            await interaction.response.defer()
            return

        idx = button.index
        if idx in self.revealed_indices:
            await interaction.response.defer()
            return

        if idx in self.bomb_positions:
            # Hit a bomb
            self.game_over = True
            button.style = discord.ButtonStyle.danger
            button.label = "\u200b"

            # Reveal rest of board
            for item in self.children:
                if isinstance(item, MinesButton):
                    item.disabled = True
                    if item.index in self.bomb_positions and item.index != idx:
                        item.style = discord.ButtonStyle.danger
                        item.label = "\u200b"
                    elif item.index in self.revealed_indices:
                        item.style = discord.ButtonStyle.success
                        item.label = "\u200b"
                elif item == self.cashout_btn:
                    item.disabled = True

            embed = self.get_game_embed(status="lost")
            await interaction.response.edit_message(embed=embed, view=self)

            end_active_game(self.user_id)
            asyncio.create_task(sync_website_deposit(self.user_id, -self.bet_amount, get_user(self.user_id)[0]))
            return

        # Safe tile found
        self.revealed_indices.add(idx)
        record_mines_click(self.user_id, idx)  # track click for pattern analysis
        button.style = discord.ButtonStyle.success
        button.label = "\u200b"
        button.disabled = True

        revealed_count = len(self.revealed_indices)
        if revealed_count == self.safe_tiles:
            # Won entire board!
            self.game_over = True
            payout = self.current_payout
            add_balance(self.user_id, payout)

            for item in self.children:
                if isinstance(item, MinesButton):
                    item.disabled = True
                    if item.index in self.bomb_positions:
                        item.style = discord.ButtonStyle.danger
                        item.label = "\u200b"
                elif item == self.cashout_btn:
                    item.disabled = True

            embed = self.get_game_embed(status="all_cleared", cashout_amt=payout)
            await interaction.response.edit_message(embed=embed, view=self)
            end_active_game(self.user_id)
            asyncio.create_task(sync_website_deposit(self.user_id, payout - self.bet_amount, get_user(self.user_id)[0]))
            return

        # Update cashout button
        self.cashout_btn.disabled = False
        self.cashout_btn.label = f"Cashout ({self.current_payout:,.2f})"

        embed = self.get_game_embed(status="active")
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return

        if self.game_over or len(self.revealed_indices) == 0:
            await interaction.response.defer()
            return

        self.game_over = True
        payout = self.current_payout
        add_balance(self.user_id, payout)

        for item in self.children:
            if isinstance(item, MinesButton):
                item.disabled = True
                if item.index in self.bomb_positions:
                    item.style = discord.ButtonStyle.danger
                    item.label = "\u200b"
            elif item == self.cashout_btn:
                item.disabled = True

        embed = self.get_game_embed(status="win", cashout_amt=payout)
        await interaction.response.edit_message(embed=embed, view=self)
        end_active_game(self.user_id)
        asyncio.create_task(sync_website_deposit(self.user_id, payout - self.bet_amount, get_user(self.user_id)[0]))


@bot.tree.command(name="mines", description="Play Mines. Pick safe tiles and avoid bombs.")
@app_commands.describe(
    amount="Bet amount in dices",
    bombs="Number of bombs to hide in the grid (1 to 23)",
)
async def mines(
    interaction: discord.Interaction,
    amount: float,
    bombs: int,
):
    total_tiles = 24

    if amount <= 0:
        await interaction.response.send_message("Bet amount must be greater than 0.", ephemeral=True)
        return

    if bombs < 1 or bombs >= total_tiles:
        await interaction.response.send_message(
            f"Bombs must be between 1 and {total_tiles - 1}.",
            ephemeral=True,
        )
        return

    total_bal = get_total_balance(interaction.user.id)
    if amount > total_bal:
        await interaction.response.send_message(
            f"Not enough balance. You have **{total_bal:,.2f}** dices.",
            ephemeral=True,
        )
        return

    # Deduct bet upfront
    add_balance(interaction.user.id, -amount)
    start_active_game(interaction.user.id, "Mines", amount)

    view = MinesView(
        user_id=interaction.user.id,
        bet_amount=amount,
        bombs=bombs,
    )
    embed = view.get_game_embed(status="active")
    await interaction.response.send_message(embed=embed, view=view)


DICE_FACES_DIR = os.path.join(os.path.dirname(__file__), "assets", "dice")


class DiceDuelView(discord.ui.View):
    def __init__(self, p1: discord.Member, bet: float, target_wins: int):
        super().__init__(timeout=180)
        self.p1 = p1
        self.p2: discord.Member = None
        self.bet = bet
        self.target_wins = target_wins
        self.p1_score = 0
        self.p2_score = 0
        self.current_turn = 1  # 1 for p1, 2 for p2
        self.round_num = 1
        self.p1_roll = None
        self.p2_roll = None
        self.state = "lobby"  # "lobby", "playing", "finished"

        # Lobby buttons
        self.join_btn = discord.ui.Button(label="Join Duel", style=discord.ButtonStyle.primary, row=0)
        self.join_btn.callback = self.handle_join
        self.add_item(self.join_btn)

        self.bot_btn = discord.ui.Button(label="Call Bot", style=discord.ButtonStyle.secondary, row=0)
        self.bot_btn.callback = self.handle_play_bot
        self.add_item(self.bot_btn)

        self.cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
        self.cancel_btn.callback = self.handle_cancel
        self.add_item(self.cancel_btn)

        # Roll button (hidden during lobby)
        self.roll_btn = discord.ui.Button(label="Roll Dice", style=discord.ButtonStyle.primary, row=0)
        self.roll_btn.callback = self.handle_roll

    def get_dice_file(self, roll: int) -> discord.File:
        fp = os.path.join(DICE_FACES_DIR, f"dice_{roll}.png")
        if os.path.exists(fp):
            return discord.File(fp, filename=f"dice_{roll}.png")
        return None

    def build_embed(self, last_desc: str = "") -> discord.Embed:
        if self.state == "lobby":
            embed = discord.Embed(
                title="Dice Duel Challenge!",
                description=(
                    f"**Challenger:** {self.p1.mention}\n"
                    f"**Entry Bet:** **{self.bet:,.2f}** dices each\n"
                    f"**First To:** **{self.target_wins}** win(s)\n"
                    f"**Prize:** **{(self.bet * 2 * 0.95):,.2f}** dices\n\n"
                    f"*Click **Join Duel** to accept or **Call Bot**!*"
                ),
                color=0x0498fb,
            )
            return embed

        turn_user = self.p1 if self.current_turn == 1 else self.p2
        score_bar = f"**{self.p1.display_name}** ({self.p1_score}/{self.target_wins})  VS  **{self.p2.display_name}** ({self.p2_score}/{self.target_wins})"

        if self.state == "playing":
            embed = discord.Embed(
                title=f"Dice Duel — Round {self.round_num}",
                description=f"{score_bar}\n\n{last_desc}\nTurn: **{turn_user.mention}** — click **Roll Dice**!",
                color=0x0498fb,
            )
        else:
            # finished
            winner = self.p1 if self.p1_score >= self.target_wins else self.p2
            prize = round(self.bet * 2 * 0.95, 2)
            embed = discord.Embed(
                title="Dice Duel — Champion!",
                description=(
                    f"{score_bar}\n\n"
                    f"**{winner.mention}** wins the duel with **{max(self.p1_score, self.p2_score)}** win(s)!\n"
                    f"Prize: **+{prize:,.2f}** dices (1.90x)"
                ),
                color=0x0498fb,
            )
        return embed

    async def handle_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.p1.id:
            await interaction.response.send_message("Only the creator can cancel this duel.", ephemeral=True)
            return
        if self.state != "lobby":
            await interaction.response.send_message("The duel has already started.", ephemeral=True)
            return

        self.state = "finished"
        self.clear_items()
        add_balance(self.p1.id, self.bet, tx_type="duel_refund")
        end_active_game(self.p1.id)
        embed = discord.Embed(
            title="Duel Cancelled",
            description=f"Duel was cancelled by {self.p1.mention}. Refunded **{self.bet:,.2f}** dices.",
            color=0x0498fb,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_play_bot(self, interaction: discord.Interaction):
        if self.state != "lobby":
            await interaction.response.send_message("Duel is no longer in lobby.", ephemeral=True)
            return
        if interaction.user.id != self.p1.id:
            await interaction.response.send_message("Only the lobby creator can start vs Bot.", ephemeral=True)
            return

        self.p2 = interaction.client.user
        self.state = "playing"
        self.clear_items()
        self.add_item(self.roll_btn)

        embed = self.build_embed(last_desc=f"🤖 **{self.p2.mention}** accepted the challenge!\nIt's **{self.p1.mention}**'s turn to roll first.")
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_join(self, interaction: discord.Interaction):
        if self.state != "lobby":
            await interaction.response.send_message("Duel is no longer in lobby.", ephemeral=True)
            return
        if interaction.user.id == self.p1.id:
            await interaction.response.send_message("You cannot play against yourself! Click Play vs Bot instead.", ephemeral=True)
            return

        p2_bal = get_total_balance(interaction.user.id)
        if p2_bal < self.bet:
            await interaction.response.send_message(
                f"You need **{self.bet:,.2f}** dices to join, but only have **{p2_bal:,.2f}**.",
                ephemeral=True,
            )
            return

        # Deduct bet from player 2
        add_balance(interaction.user.id, -self.bet, tx_type="bet")
        start_active_game(interaction.user.id, "DiceDuel", self.bet)

        self.p2 = interaction.user
        self.state = "playing"
        self.clear_items()
        self.add_item(self.roll_btn)

        embed = self.build_embed(last_desc=f"**{self.p2.mention}** joined the duel!\nIt's **{self.p1.mention}**'s turn to roll first.")
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_roll(self, interaction: discord.Interaction):
        if self.state != "playing":
            await interaction.response.send_message("The game is not currently active.", ephemeral=True)
            return

        expected_user = self.p1 if self.current_turn == 1 else self.p2
        if interaction.user.id != expected_user.id:
            await interaction.response.send_message(f"It's not your turn! Waiting for {expected_user.mention}.", ephemeral=True)
            return

        roll_val = random.randint(1, 6)
        dice_file = self.get_dice_file(roll_val)

        if self.current_turn == 1:
            self.p1_roll = roll_val
            desc = f"🎲 **{self.p1.display_name}** rolled a **{self.p1_roll}**!\n"

            # Check if opponent is bot
            if getattr(self.p2, "bot", False):
                # Bot rolls automatically with +20% win chance boost
                bot_roll = random.randint(1, 6)
                # 20% bias: if bot rolled less than or equal to p1, 20% chance to boost roll above p1
                if random.random() < 0.20 and self.p1_roll < 6:
                    bot_roll = random.randint(self.p1_roll + 1, 6)
                elif random.random() < 0.20 and self.p1_roll == 6:
                    bot_roll = 6  # force tie if possible

                self.p2_roll = bot_roll
                bot_dice_file = self.get_dice_file(self.p2_roll)

                round_desc = f"🎲 **{self.p1.display_name}** rolled a **{self.p1_roll}**\n🤖 **{self.p2.display_name}** rolled a **{self.p2_roll}**\n"
                if self.p1_roll > self.p2_roll:
                    self.p1_score += 1
                    round_desc += f"💥 **{self.p1.display_name}** wins Round {self.round_num}!\n"
                elif self.p2_roll > self.p1_roll:
                    self.p2_score += 1
                    round_desc += f"💥 🤖 **{self.p2.display_name}** wins Round {self.round_num}!\n"
                else:
                    round_desc += f"🤝 Tie! Both rolled **{self.p1_roll}** — round replayed!\n"

                if self.p1_score >= self.target_wins or self.p2_score >= self.target_wins:
                    self.state = "finished"
                    self.clear_items()
                    winner = self.p1 if self.p1_score >= self.target_wins else self.p2
                    prize = round(self.bet * 2 * 0.95, 2)
                    if winner == self.p1:
                        add_balance(self.p1.id, prize, tx_type="duel_win")
                        asyncio.create_task(sync_website_deposit(self.p1.id, prize - self.bet, get_user(self.p1.id)[0]))
                    end_active_game(self.p1.id)

                    embed = self.build_embed(last_desc=round_desc)
                    if bot_dice_file:
                        embed.set_image(url=f"attachment://dice_{self.p2_roll}.png")
                        await interaction.response.edit_message(embed=embed, view=self, attachments=[bot_dice_file])
                    else:
                        await interaction.response.edit_message(embed=embed, view=self)
                else:
                    self.round_num += 1
                    self.current_turn = 1
                    self.p1_roll = None
                    self.p2_roll = None
                    embed = self.build_embed(last_desc=round_desc)
                    if bot_dice_file:
                        embed.set_image(url=f"attachment://dice_{self.p2_roll}.png")
                        await interaction.response.edit_message(embed=embed, view=self, attachments=[bot_dice_file])
                    else:
                        await interaction.response.edit_message(embed=embed, view=self)
                return

            self.current_turn = 2
            embed = self.build_embed(last_desc=desc)
            if dice_file:
                embed.set_image(url=f"attachment://dice_{roll_val}.png")
                await interaction.response.edit_message(embed=embed, view=self, attachments=[dice_file])
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            # Player 2 (human) rolled -> resolve round
            self.p2_roll = roll_val
            round_desc = f"🎲 **{self.p1.display_name}** rolled a **{self.p1_roll}**\n🎲 **{self.p2.display_name}** rolled a **{self.p2_roll}**\n"

            if self.p1_roll > self.p2_roll:
                self.p1_score += 1
                round_desc += f"💥 **{self.p1.display_name}** wins Round {self.round_num}!\n"
            elif self.p2_roll > self.p1_roll:
                self.p2_score += 1
                round_desc += f"💥 **{self.p2.display_name}** wins Round {self.round_num}!\n"
            else:
                round_desc += f"🤝 Tie! Both rolled **{self.p1_roll}** — round replayed!\n"

            # Check if someone reached target_wins
            if self.p1_score >= self.target_wins or self.p2_score >= self.target_wins:
                self.state = "finished"
                self.clear_items()
                winner = self.p1 if self.p1_score >= self.target_wins else self.p2
                loser = self.p2 if winner == self.p1 else self.p1
                prize = round(self.bet * 2 * 0.95, 2)
                add_balance(winner.id, prize, tx_type="duel_win")
                end_active_game(self.p1.id)
                end_active_game(self.p2.id)

                # Sync web deposits
                asyncio.create_task(sync_website_deposit(winner.id, prize - self.bet, get_user(winner.id)[0]))
                asyncio.create_task(sync_website_deposit(loser.id, -self.bet, get_user(loser.id)[0]))

                embed = self.build_embed(last_desc=round_desc)
                if dice_file:
                    embed.set_image(url=f"attachment://dice_{roll_val}.png")
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[dice_file])
                else:
                    await interaction.response.edit_message(embed=embed, view=self)
            else:
                self.round_num += 1
                self.current_turn = 1
                self.p1_roll = None
                self.p2_roll = None
                embed = self.build_embed(last_desc=round_desc)
                if dice_file:
                    embed.set_image(url=f"attachment://dice_{roll_val}.png")
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[dice_file])
                else:
                    await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.state == "finished":
            return
        if self.state == "lobby":
            # Refund player 1
            add_balance(self.p1.id, self.bet, tx_type="duel_refund")
            end_active_game(self.p1.id)
        elif self.state == "playing":
            # Game timed out mid-play: refund both players
            add_balance(self.p1.id, self.bet, tx_type="duel_refund")
            if self.p2:
                add_balance(self.p2.id, self.bet, tx_type="duel_refund")
                end_active_game(self.p2.id)
            end_active_game(self.p1.id)
        self.state = "finished"
        self.clear_items()


@bot.tree.command(name="diceduel", description="Challenge another player to a 2-player dice duel!")
@app_commands.describe(
    amount="Bet amount in dices each player puts in",
    first_to="First to how many round wins? (1, 2, or 3)",
)
@app_commands.choices(first_to=[
    app_commands.Choice(name="First to 1 win", value=1),
    app_commands.Choice(name="First to 2 wins", value=2),
    app_commands.Choice(name="First to 3 wins", value=3),
])
async def diceduel(
    interaction: discord.Interaction,
    amount: float,
    first_to: int = 1,
):
    if amount <= 0:
        await interaction.response.send_message("Bet amount must be greater than 0.", ephemeral=True)
        return

    if first_to not in [1, 2, 3]:
        await interaction.response.send_message("Target wins must be 1, 2, or 3.", ephemeral=True)
        return

    p1_bal = get_total_balance(interaction.user.id)
    if amount > p1_bal:
        await interaction.response.send_message(
            f"Not enough balance. You have **{p1_bal:,.2f}** dices.",
            ephemeral=True,
        )
        return

    # Deduct bet upfront from creator
    add_balance(interaction.user.id, -amount, tx_type="bet")
    start_active_game(interaction.user.id, "DiceDuel", amount)

    view = DiceDuelView(p1=interaction.user, bet=amount, target_wins=first_to)
    embed = view.build_embed()
    await interaction.response.send_message(embed=embed, view=view)



ALLOWED_TIPPER_ID = 1079074717799030824


@bot.tree.command(name="tip", description="Tip dices to another user")
@app_commands.describe(
    user="The user to tip",
    amount="Amount of dices to tip",
    wager_req="Wager requirement multiplier before recipient can withdraw (0 = none)",
    can_withdraw="Whether the recipient can withdraw these funds (default True)",
)
async def tip(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: float,
    wager_req: float = 0.0,
    can_withdraw: bool = True,
):
    if interaction.user.id != ALLOWED_TIPPER_ID:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("You cannot tip yourself.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    if wager_req < 0:
        await interaction.response.send_message("Wager requirement cannot be negative.", ephemeral=True)
        return

    withdrawable = get_withdrawable_balance(interaction.user.id)
    if amount > withdrawable:
        total = get_total_balance(interaction.user.id)
        promo = total - withdrawable
        msg = f"Not enough tippable balance. You have **{withdrawable:,.2f}** tippable dices."
        if promo > 0:
            msg += f"\n*(You have **{promo:,.2f}** in credited/promo bonus that cannot be tipped or withdrawn. Play games to turn them into real winnings!)*"
        await interaction.response.send_message(msg, ephemeral=True)
        return

    # Determine if this tip is promo (non-withdrawable / has wager requirement)
    is_promo = (not can_withdraw) or (wager_req > 0)
    wager_amount = round(amount * wager_req, 8) if wager_req > 0 else 0.0

    # Deduct from tipper (clean balance)
    add_balance(interaction.user.id, -amount)
    # Credit recipient (promo or clean)
    add_balance(user.id, amount, is_promo=is_promo, add_wager=wager_amount)

    sender_new, _, _, _ = get_user(interaction.user.id)
    recipient_new, _, _, _ = get_user(user.id)

    # Send DM to the recipient
    try:
        dm_desc = f"Your new balance: **{recipient_new:,.2f}** dices"
        if wager_req > 0:
            dm_desc += f"\n*(Wager **{wager_amount:,.2f}** dices to unlock withdrawal)*"
        elif not can_withdraw:
            dm_desc += "\n*(This tip cannot be withdrawn — play to earn real balance!)*"
        embed = discord.Embed(
            title=f"\"{interaction.user.display_name}\" Tipped You {amount:,.2f}!",
            description=dm_desc,
            color=0x0498fb,
        )
        await user.send(embed=embed)
    except Exception as e:
        print(f"[Tip DM Error] Could not DM user {user.id}: {e}")

    # Confirm in channel
    confirm_lines = [f"Successfully tipped **{amount:,.2f}** dices to {user.mention}."]
    if wager_req > 0:
        confirm_lines.append(f"Wager requirement set: **{wager_amount:,.2f}** dices before they can withdraw.")
    elif not can_withdraw:
        confirm_lines.append("Recipient **cannot withdraw** this tip — promo only.")
    confirm_lines.append(f"Your remaining balance: **{sender_new:,.2f}** dices.")
    confirm_embed = discord.Embed(
        title="Tip Sent!",
        description="\n".join(confirm_lines),
        color=0x0498fb,
    )
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


@bot.tree.command(name="clearall", description="Reset ALL user balances to 0")
@app_commands.default_permissions(administrator=True)
async def clearall(interaction: discord.Interaction):
    cur = db.execute("SELECT COUNT(*) FROM users WHERE balance != 0 OR promo_balance != 0 OR wager_required != 0")
    count = cur.fetchone()[0]
    db.execute("UPDATE users SET balance = 0, promo_balance = 0, wager_required = 0")
    db.commit()
    embed = discord.Embed(
        title="Balances Cleared",
        description=f"Reset **{count}** user balance(s) to 0.",
        color=0x0498fb,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="add", description="Add withdrawable balance to a user")
@app_commands.describe(
    user="The user to give balance to",
    amount="Amount of dices to add",
)
async def add_cmd(interaction: discord.Interaction, user: discord.Member, amount: float):
    if interaction.user.id != ALLOWED_TIPPER_ID:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Add as real clean balance — fully withdrawable and tippable
        add_balance(user.id, amount, tx_type="deposit")

        new_bal, _, _, _ = get_user(user.id)

        try:
            embed = discord.Embed(
                title=f"\"{interaction.user.display_name}\" Tipped You {amount:,.2f}!",
                description=f"Your new balance: **{new_bal:,.2f}** dices",
                color=0x0498fb,
            )
            await user.send(embed=embed)
        except Exception as e:
            print(f"[Add DM Error] Could not DM user {user.id}: {e}")

        confirm_embed = discord.Embed(
            title="Balance Added!",
            description=f"Added **{amount:,.2f}** dices to {user.mention}.\nTheir new balance: **{new_bal:,.2f}** dices.",
            color=0x0498fb,
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)
    except Exception as e:
        print(f"[Add Error] {e}")
        await interaction.followup.send(f"Error adding balance: {e}", ephemeral=True)



@bot.tree.command(name="remove", description="Remove balance from a user")
@app_commands.describe(
    user="The user to remove balance from",
    amount="Amount of dices to remove",
)
async def remove_cmd(interaction: discord.Interaction, user: discord.Member, amount: float):
    if interaction.user.id != ALLOWED_TIPPER_ID:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    total = get_total_balance(user.id)
    if amount > total:
        await interaction.response.send_message(
            f"{user.mention} only has **{total:,.2f}** dices. Can't remove more than they have.",
            ephemeral=True,
        )
        return

    # Deduct from promo first, then real balance
    add_balance(user.id, -amount)

    new_bal, _, new_promo, _ = get_user(user.id)
    new_total = new_bal + new_promo

    confirm_embed = discord.Embed(
        title="Balance Removed",
        description=f"Removed **{amount:,.2f}** dices from {user.mention}.\nTheir new balance: **{new_total:,.2f}** dices.",
        color=0x0498fb,
    )
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


@bot.tree.command(name="clear", description="[Owner] Clear a user's profit history")
@app_commands.describe(user="The user whose profit history to clear")
async def clear_cmd(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != ALLOWED_TIPPER_ID:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    uid = user.id
    db.execute("DELETE FROM transactions WHERE user_id=?", (uid,))
    db.commit()

    embed = discord.Embed(
        title="Profit Cleared",
        description=f"All transaction history for {user.mention} has been cleared.\nTheir `/profit` page is now empty.",
        color=0x0498fb,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


def build_profit_html(username: str, avatar_url: str, balance: float,
                      history: list, chart_points: list, chart_labels: list) -> str:
    import json
    BUX_TO_USD = 0.002

    # Compute stats
    total_profit = sum(r["amount"] for r in history if r["type"] in ("Win", "Deposit"))
    total_profit_usd = round(total_profit * BUX_TO_USD, 2)
    total_profit_bux = round(total_profit, 2)
    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000
    profit_24h = sum(r["amount"] for r in history
                     if r["type"] in ("Win", "Deposit") and (now_ms - r["timestamp_ms"]) < day_ms)
    profit_24h_usd = round(profit_24h * BUX_TO_USD, 2)
    profit_24h_bux = round(profit_24h, 2)
    balance_bux = round(balance, 2)

    data = json.dumps({
        "username": username,
        "avatar": avatar_url,
        "total_earnings_bux": total_profit_bux,
        "total_earnings_usd": total_profit_usd,
        "earnings_24h_bux": profit_24h_bux,
        "earnings_24h_usd": profit_24h_usd,
        "current_balance_bux": balance_bux,
        "history": history,
        "chart_points": chart_points,
        "chart_labels": chart_labels,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Profit — {username}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
body{{background:#0a0a0c;color:#f5f5f7;min-height:100vh;display:flex;align-items:flex-start;justify-content:center}}
.fomo-page{{width:1180px;padding:24px 24px 40px;display:flex;flex-direction:column;gap:20px}}
.fomo-banner{{width:100%;height:110px;background:#12111a;border-radius:12px;margin-bottom:-28px;position:relative;z-index:1}}
.fomo-profile-row{{display:flex;align-items:flex-end;gap:16px;padding:0 8px;margin-top:8px;position:relative;z-index:2}}
.fomo-avatar{{width:80px;height:80px;border-radius:50%;border:3px solid #0a0a0c;object-fit:cover;background:#1d1c2d}}
.fomo-profile-info{{display:flex;flex-direction:column;gap:4px;padding-bottom:8px}}
.fomo-username{{font-size:22px;font-weight:700;color:#f5f5f7}}
.fomo-handle{{font-size:13px;color:#6b6b80}}
.chart-card{{background:#12111a;border-radius:12px;padding:20px;border:1px solid rgba(255,255,255,0.06)}}
.chart-title{{font-size:13px;font-weight:600;color:#9090a0;margin-bottom:14px}}
.chart-wrap{{height:220px;position:relative}}
.history-card{{background:#12111a;border-radius:12px;padding:20px;border:1px solid rgba(255,255,255,0.06)}}
.history-title{{font-size:13px;font-weight:600;color:#9090a0;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse}}
th{{font-size:11px;color:#4b4b60;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:6px 12px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.05)}}
td{{font-size:13px;color:#c5c5d0;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.04)}}
td:last-child{{text-align:right;font-weight:600}}
.badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase}}
.badge-deposit{{background:rgba(0,210,90,0.15);color:#00d25a}}
.badge-win{{background:rgba(4,152,251,0.15);color:#0498fb}}
.badge-bet,.badge-lose,.badge-lost{{background:rgba(255,60,60,0.12);color:#ff4040}}
.badge-withdraw{{background:rgba(255,180,0,0.12);color:#ffb400}}
.pos{{color:#00d25a}}.neg{{color:#ff4040}}
</style>
</head>
<body>
<div class="fomo-page" id="root"></div>
<script>
const D = {data};
const BUX = 0.002;
function fmt(n){{return Number(n).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}
function badge(t){{
  const m={{"Deposit":"deposit","Win":"win","Bet":"bet","Lose":"lose","Lost":"lost","Withdraw":"withdraw"}};
  const c=m[t]||"bet";
  return `<span class="badge badge-${{c}}">${{t}}</span>`;
}}
const root=document.getElementById('root');
root.innerHTML=`
<div class="fomo-banner"></div>
<div class="fomo-profile-row">
  <img class="fomo-avatar" src="${{D.avatar}}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'" alt="avatar"/>
  <div class="fomo-profile-info">
    <div class="fomo-username">${{D.username}}</div>
    <div class="fomo-handle">@${{D.username}}</div>
  </div>
</div>
<div class="chart-card">
  <div class="chart-title">Balance History (Last 24h Bets)</div>
  <div class="chart-wrap"><canvas id="chart"></canvas></div>
</div>
<div class="history-card">
  <div class="history-title">Recent Transactions</div>
  <table>
    <thead><tr><th>Type</th><th>When</th><th>Amount</th><th>Balance After</th></tr></thead>
    <tbody>${{D.history.filter(r=>r.type==='Deposit'||r.type==='Withdraw').slice(0,8).map(r=>`
      <tr>
        <td>${{badge(r.type)}}</td>
        <td>${{r.when}}</td>
        <td class="${{r.amount>=0?'pos':'neg'}}">${{r.amount>=0?'+':''}}${{fmt(r.amount)}}</td>
        <td>${{fmt(r.balance_after)}}</td>
      </tr>`).join('')}}
    </tbody>
  </table>
</div>`;
// Chart
const pts=D.chart_points, lbls=D.chart_labels;
const isUp=pts.length<2||(pts[pts.length-1]>=pts[0]);
const lineColor=isUp?'#0498fb':'#ff4040';
new Chart(document.getElementById('chart'),{{
  type:'line',
  data:{{labels:lbls,datasets:[{{
    data:pts,
    borderColor:lineColor,
    borderWidth:2.5,
    pointRadius:3,
    pointHoverRadius:6,
    pointBackgroundColor:lineColor,
    pointBorderColor:'#0a0a0c',
    pointBorderWidth:2,
    tension:0.4,
    fill:true,
    backgroundColor:(ctx)=>{{
      const g=ctx.chart.ctx.createLinearGradient(0,0,0,180);
      g.addColorStop(0,isUp?'rgba(4,152,251,0.3)':'rgba(255,64,64,0.3)');
      g.addColorStop(1,'rgba(0,0,0,0)');
      return g;
    }}
  }}]}},
  options:{{
    responsive:true,
    maintainAspectRatio:false,
    interaction:{{mode:'index',intersect:false}},
    plugins:{{
      legend:{{display:false}},
      tooltip:{{
        backgroundColor:'#1a1a2e',
        borderColor:'rgba(255,255,255,0.1)',
        borderWidth:1,
        titleColor:'#9090a0',
        bodyColor:'#f5f5f7',
        padding:10,
        callbacks:{{
          title:(items)=>items[0].label,
          label:(item)=>`Balance: ${{Number(item.raw).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}} dices`
        }}
      }}
    }},
    scales:{{
      x:{{
        display:true,
        ticks:{{color:'#4b4b60',font:{{size:10}},maxTicksLimit:6,maxRotation:0}},
        grid:{{display:false}},
        border:{{display:false}}
      }},
      y:{{
        display:true,
        position:'right',
        ticks:{{
          color:'#4b4b60',
          font:{{size:10}},
          maxTicksLimit:4,
          callback:(v)=>Number(v).toLocaleString('en-US',{{maximumFractionDigits:0}})
        }},
        grid:{{color:'rgba(255,255,255,0.04)'}},
        border:{{display:false}}
      }}
    }}
  }}
}});
</script>
</body></html>"""


async def generate_profit_card(target: discord.Member) -> io.BytesIO:
    import json, tempfile, os, aiohttp
    from playwright.async_api import async_playwright

    uid = target.id
    import datetime

    # Fetch all transactions from SQLite
    rows = db.execute(
        "SELECT type, amount, balance_after, ts FROM transactions WHERE user_id=? ORDER BY ts DESC LIMIT 50",
        (uid,),
    ).fetchall()
    bal, _, promo, _ = get_user(uid)
    current_balance = bal + promo

    # Build history list
    history = []
    for tx_type, amount, balance_after, ts in rows:
        dt = datetime.datetime.fromtimestamp(ts)
        when_str = f"{dt.month}/{dt.day}/{dt.year}, {dt.strftime('%I:%M %p').lstrip('0')}"
        history.append({
            "type": tx_type.capitalize(),
            "amount": round(float(amount), 2),
            "balance_after": round(float(balance_after), 2),
            "when": when_str,
            "timestamp_ms": int(ts * 1000),
        })

    # Build chart data from recorded bets in the last 24h
    now_ts = time.time()
    ts_24h_ago = now_ts - 86400

    chart_rows = db.execute(
        "SELECT balance_after, ts FROM transactions WHERE user_id=? AND type='bet' AND ts >= ? ORDER BY ts ASC",
        (uid, ts_24h_ago),
    ).fetchall()

    if chart_rows:
        step = max(1, len(chart_rows) // 16)
        sampled = chart_rows[::step]
        # Include the most recent bet if not already included
        if chart_rows[-1] not in sampled:
            sampled.append(chart_rows[-1])
        chart_points = [round(float(r[0]), 2) for r in sampled]
        chart_labels = [datetime.datetime.fromtimestamp(r[1]).strftime("%I:%M %p").lstrip("0") for r in sampled]
    else:
        # If no bets in last 24h, check if there's any recent bet
        latest_bet = db.execute(
            "SELECT balance_after, ts FROM transactions WHERE user_id=? AND type='bet' ORDER BY ts DESC LIMIT 1",
            (uid,),
        ).fetchone()
        if latest_bet:
            chart_points = [round(float(latest_bet[0]), 2), round(float(latest_bet[0]), 2)]
            lbl = datetime.datetime.fromtimestamp(latest_bet[1]).strftime("%I:%M %p").lstrip("0")
            chart_labels = [lbl, "Now"]
        else:
            chart_points = [current_balance, current_balance]
            chart_labels = ["24h ago", "Now"]

    # Get Discord avatar URL
    avatar_url = str(target.display_avatar.replace(size=256, format="png"))

    # Generate HTML
    html = build_profit_html(
        username=target.display_name,
        avatar_url=avatar_url,
        balance=current_balance,
        history=history,
        chart_points=chart_points,
        chart_labels=chart_labels,
    )

    # Write to temp file and screenshot with Playwright
    tmp_path = os.path.join(tempfile.gettempdir(), f"profit_{uid}.html")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(html)

    file_url = f"file:///{tmp_path.replace(os.sep, '/')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1230, "height": 900})
        try:
            await page.goto(file_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_selector(".fomo-page", timeout=8000)
            element = page.locator(".fomo-page")
            screenshot = await element.screenshot()
        finally:
            await browser.close()

    try:
        os.remove(tmp_path)
    except Exception:
        pass

    return io.BytesIO(screenshot)





@bot.tree.command(name="profit", description="Show a user's profit card with chart and history")
@app_commands.describe(user="The user to check profit for")
async def profit_cmd(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    try:
        buf = await generate_profit_card(user)
        file = discord.File(buf, filename="profit.png")
        await interaction.followup.send(file=file)
    except Exception as e:
        await interaction.followup.send(f"Failed to generate profit card: {e}", ephemeral=True)
        raise


async def poll_pending_deposits():
    """
    Periodically checks the website for uncredited Plisio deposits.
    Ensures deposits work even when the bot cannot receive direct inbound webhooks.
    """
    import aiohttp
    await bot.wait_until_ready()
    print("[Deposit Poller] Started background polling for deposits...")
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{SITE_URL}/api/plisio/pending-deposits",
                    headers={"Authorization": f"Bearer {BOT_INTERNAL_SECRET}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        deposits = data.get("deposits", [])
                        for dep in deposits:
                            dep_id = dep.get("id")
                            discord_id = int(dep.get("discordId"))
                            amount = float(dep.get("amount", 0))

                            if amount > 0:
                                add_balance(discord_id, amount, tx_type="deposit")
                                new_bal, _, _, _ = get_user(discord_id)
                                print(f"[Deposit Poller] Credited user {discord_id} with {amount}. New Balance: {new_bal}")

                                asyncio.create_task(notify_user_deposit(discord_id, amount, new_bal))
                                asyncio.create_task(sync_website_deposit(discord_id, amount, new_bal))

                            # Acknowledge and remove from queue
                            await session.post(
                                f"{SITE_URL}/api/plisio/pending-deposits",
                                headers={"Authorization": f"Bearer {BOT_INTERNAL_SECRET}"},
                                json={"id": dep_id},
                                timeout=aiohttp.ClientTimeout(total=5),
                            )
        except Exception as e:
            # Silent retry
            pass
        await asyncio.sleep(4)


async def run_bot_and_server():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable")
    await start_http_server()
    asyncio.create_task(poll_pending_deposits())
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(run_bot_and_server())

