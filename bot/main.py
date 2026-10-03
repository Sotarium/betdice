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

SITE_URL = os.getenv(
    "SITE_URL",
    "https://betdice-frouxzys-projects-fcc3f71b.vercel.app",
)
BOT_INTERNAL_SECRET = os.getenv("BOT_INTERNAL_SECRET", "betdice_secret")
BOT_PORT = int(os.getenv("PORT", os.getenv("BOT_PORT", "8080")))

LAYOUT = {
    "important": [
        ("🎫・ticket", False),
        ("📢・news", True),
        ("📩・invite-rewards", False),
        ("🔨・event", False),
        ("💝・giveaway", False),
        ("🚀-invite", False),
    ],
    "🎲・PLAY": [
        ("💰-history", True),
        ("💸・play-1", False),
        ("💸・play-2", False),
        ("💸・play-3", False),
    ],
    "💬・COMMUNITY": [
        ("✉️・general", False),
        ("✅・vouch", False),
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
db.commit()


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
                color=0x2B2D31,
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


async def get_deposit_address(discord_id: int, username: str, avatar_hash):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SITE_URL}/api/plisio/deposit",
            json={"discordId": str(discord_id)},  # SOL + LTC
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
                f"❌ **Withdrawal Failed:** {payout_error}\nYour balance of **{amt:,.2f}** dices has been refunded.",
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
            title="✅ Withdrawal Sent!",
            description=(
                f"**Amount:** {amt:,.2f} dices\n"
                f"**Currency:** {currency}\n"
                f"**Address:** `{target_addr}`{tx_info}\n\n"
                "The payout has been broadcast to the blockchain."
            ),
            color=0x00E676,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class BalanceView(discord.ui.View):
    def __init__(self, target_id: int):
        super().__init__(timeout=180)
        self.target_id = target_id

    @discord.ui.button(label="Deposit", style=discord.ButtonStyle.secondary)
    async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This is not your balance.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        avatar_hash = interaction.user.avatar.key if interaction.user.avatar else None
        try:
            status, data = await get_deposit_address(
                interaction.user.id,
                interaction.user.name,
                avatar_hash,
            )
        except Exception as e:
            await interaction.followup.send(f"Network error: `{e}`", ephemeral=True)
            return

        addresses = data.get("addresses") or []
        if status != 200 or (not addresses and not data.get("address")):
            err = data.get("error", str(data)[:200])
            await interaction.followup.send(
                f"Could not get deposit address.\n`{err}`\n\n"
                "On Plisio:\n"
                "• Enable **White-label**\n"
                "• Create **SOL** and **LTC** wallets\n"
                "• Set PLISIO_SECRET_KEY on Vercel",
                ephemeral=True,
            )
            return

        if not addresses and data.get("address"):
            addresses = [{"address": data["address"], "currency": data.get("currency", "?")}]

        lines = []
        for a in addresses:
            cur = (a.get("currency") or "?").upper()
            addr = a.get("address") or "?"
            if cur == "SOL":
                lines.append(f"**Solana (SOL)**\n```{addr}```")
            elif cur == "LTC":
                lines.append(f"**Litecoin (LTC)**\n```{addr}```")
            else:
                lines.append(f"**{cur}**\n```{addr}```")

        embed = discord.Embed(
            title="Deposit",
            description=(
                "Send **any amount** to your permanent address:\n\n"
                + "\n\n".join(lines)
                + "\n\nWrong network = lost funds.\n"
                "Balance updates after Plisio confirms."
            ),
            color=0x2B2D31,
        )
        embed.set_footer(text="Unique addresses for your account · SOL + LTC")
        await interaction.followup.send(embed=embed, ephemeral=True)

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
        color=0x2B2D31,
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
    Standard provably fair casino mines multiplier with 1% house edge.
    multiplier = (1 - edge) * nCr(total, revealed) / nCr(total - bombs, revealed)
    """
    if revealed == 0:
        return 1.0
    house_edge = 0.01
    prob = math.comb(total_tiles - bombs, revealed) / math.comb(total_tiles, revealed)
    mult = (1.0 - house_edge) / prob
    return round(mult, 2)


class MinesButton(discord.ui.Button):
    def __init__(self, index: int, row: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=row)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        await view.handle_tile_click(interaction, self)


class MinesView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: float, bombs: int, grid_size: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.bombs = bombs
        self.grid_size = grid_size
        self.total_tiles = grid_size * grid_size
        self.safe_tiles = self.total_tiles - bombs
        self.revealed_indices = set()
        self.game_over = False

        # Random bomb placement
        self.bomb_positions = set(random.sample(range(self.total_tiles), self.bombs))

        # Build tile buttons
        for i in range(self.total_tiles):
            row = i // self.grid_size
            btn = MinesButton(index=i, row=row)
            self.add_item(btn)

        # Cashout button on its own row
        cashout_row = self.grid_size
        self.cashout_btn = discord.ui.Button(
            label="Cashout (0.00)",
            style=discord.ButtonStyle.success,
            disabled=True,
            row=cashout_row,
            emoji="💰",
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
                title="💣 Mines",
                description=(
                    f"**Bet:** `{self.bet_amount:,.2f}` dices\n"
                    f"**Grid:** `{self.grid_size}x{self.grid_size}` · **Bombs:** `{self.bombs}`\n"
                    f"**Gems Found:** `{revealed_count}/{self.safe_tiles}`\n"
                    f"**Multiplier:** `{self.current_multiplier:.2f}x`\n"
                    f"**Current Payout:** `+{self.current_payout:,.2f}` dices"
                ),
                color=0x2B2D31,
            )
            embed.set_footer(text="Click a tile to find gems or Cashout anytime!")
        elif status == "win":
            embed = discord.Embed(
                title="💎 Cashed Out!",
                description=(
                    f"You cashed out at **{self.current_multiplier:.2f}x**!\n"
                    f"**Profit:** `+{cashout_amt - self.bet_amount:,.2f}` dices\n"
                    f"**Total Payout:** `+{cashout_amt:,.2f}` dices"
                ),
                color=0x57F287,
            )
        elif status == "all_cleared":
            embed = discord.Embed(
                title="🏆 All Gems Cleared!",
                description=(
                    f"You found all safe gems!\n"
                    f"**Multiplier:** `{self.current_multiplier:.2f}x`\n"
                    f"**Total Payout:** `+{cashout_amt:,.2f}` dices"
                ),
                color=0xFEE75C,
            )
        else: # exploded
            embed = discord.Embed(
                title="💥 BOOM! You hit a bomb!",
                description=(
                    f"You lost **{self.bet_amount:,.2f}** dices.\n"
                    f"Gems found before explosion: `{revealed_count}`"
                ),
                color=0xED4245,
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
            # Hit a bomb!
            self.game_over = True
            button.style = discord.ButtonStyle.danger
            button.label = ""
            button.emoji = "💥"

            # Reveal rest of board
            for item in self.children:
                if isinstance(item, MinesButton):
                    item.disabled = True
                    if item.index in self.bomb_positions and item.index != idx:
                        item.style = discord.ButtonStyle.danger
                        item.emoji = "💣"
                        item.label = ""
                    elif item.index in self.revealed_indices:
                        item.style = discord.ButtonStyle.success
                        item.emoji = "💎"
                        item.label = ""
                elif item == self.cashout_btn:
                    item.disabled = True

            embed = self.get_game_embed(status="lost")
            await interaction.response.edit_message(embed=embed, view=self)

            # Sync loss to website
            asyncio.create_task(sync_website_deposit(self.user_id, -self.bet_amount, get_user(self.user_id)[0]))
            return

        # Safe gem found!
        self.revealed_indices.add(idx)
        button.style = discord.ButtonStyle.success
        button.label = ""
        button.emoji = "💎"
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
                        item.emoji = "💣"
                elif item == self.cashout_btn:
                    item.disabled = True

            embed = self.get_game_embed(status="all_cleared", cashout_amt=payout)
            await interaction.response.edit_message(embed=embed, view=self)
            asyncio.create_task(sync_website_deposit(self.user_id, payout - self.bet_amount, get_user(self.user_id)[0]))
            return

        # Update cashout button
        self.cashout_btn.disabled = False
        self.cashout_btn.label = f"Cashout ({self.current_payout:,.2f})"

        embed = self.get_game_embed(status="active")
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
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
                    item.emoji = "💣"
                    item.style = discord.ButtonStyle.danger
                    item.label = ""
            elif item == self.cashout_btn:
                item.disabled = True

        embed = self.get_game_embed(status="win", cashout_amt=payout)
        await interaction.response.edit_message(embed=embed, view=self)
        asyncio.create_task(sync_website_deposit(self.user_id, payout - self.bet_amount, get_user(self.user_id)[0]))


@bot.tree.command(name="mines", description="Play Mines! Reveal gems and avoid bombs to win")
@app_commands.describe(
    amount="Bet amount in dices",
    bombs="Number of bombs to hide in the grid",
    grid="Grid dimension: 3 for 3x3, 4 for 4x4, or 5 for 5x5"
)
@app_commands.choices(grid=[
    app_commands.Choice(name="3x3 (9 tiles)", value=3),
    app_commands.Choice(name="4x4 (16 tiles)", value=4),
    app_commands.Choice(name="5x5 (25 tiles)", value=5),
])
async def mines(
    interaction: discord.Interaction,
    amount: float,
    bombs: int,
    grid: app_commands.Choice[int],
):
    grid_size = grid.value
    total_tiles = grid_size * grid_size

    if amount <= 0:
        await interaction.response.send_message("Bet amount must be greater than 0.", ephemeral=True)
        return

    if bombs < 1 or bombs >= total_tiles:
        await interaction.response.send_message(
            f"Bombs must be between 1 and {total_tiles - 1} for a {grid_size}x{grid_size} grid.",
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

    view = MinesView(
        user_id=interaction.user.id,
        bet_amount=amount,
        bombs=bombs,
        grid_size=grid_size,
    )
    embed = view.get_game_embed(status="active")
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
            color=0x2B2D31,
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
        color=0x2B2D31,
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
        color=0xFF0000,
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
                color=0x2B2D31,
            )
            await user.send(embed=embed)
        except Exception as e:
            print(f"[Add DM Error] Could not DM user {user.id}: {e}")

        confirm_embed = discord.Embed(
            title="Balance Added!",
            description=f"Added **{amount:,.2f}** dices to {user.mention}.\nTheir new balance: **{new_bal:,.2f}** dices.",
            color=0x2B2D31,
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
        color=0xFF0000,
    )
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


async def generate_profit_card(target: discord.Member) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.patheffects as pe
    import numpy as np
    import aiohttp
    from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter

    uid = target.id

    # --- Fetch transaction history ---
    rows = db.execute(
        "SELECT type, amount, balance_after, ts FROM transactions WHERE user_id=? ORDER BY ts ASC",
        (uid,),
    ).fetchall()

    # --- Fetch deposits from transactions (type='deposit') ---
    deposit_rows = db.execute(
        "SELECT amount, ts FROM transactions WHERE user_id=? AND type='deposit' ORDER BY ts DESC LIMIT 10",
        (uid,),
    ).fetchall()

    # --- Current balance ---
    bal, _, promo, _ = get_user(uid)
    current_total = bal + promo

    # --- Build profit line data ---
    # profit = balance_after - first balance_after (so starts at 0)
    if rows:
        times = [r[3] for r in rows]
        balances = [r[2] for r in rows]
        # Normalize to profit relative to start
        start = balances[0]
        profits = [b - start for b in balances]
        # Add current point
        times.append(time.time())
        profits.append(current_total - start)
    else:
        times = [time.time() - 3600, time.time()]
        profits = [0.0, 0.0]

    profit_now = profits[-1]
    is_positive = profit_now >= 0
    line_color = "#00e676" if is_positive else "#ff1744"
    fill_color = "#00e676" if is_positive else "#ff1744"
    profit_sign = "+" if is_positive else ""

    # --- Download avatar ---
    avatar_img = None
    try:
        avatar_url = str(target.display_avatar.replace(size=128, format="png"))
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                avatar_data = await resp.read()
        avatar_img = PILImage.open(io.BytesIO(avatar_data)).convert("RGBA").resize((80, 80))
        # Circular mask
        mask = PILImage.new("L", (80, 80), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 80, 80), fill=255)
        avatar_img.putalpha(mask)
    except Exception:
        avatar_img = None

    # --- Build the card with PIL ---
    W, H = 900, 480
    card = PILImage.new("RGBA", (W, H), (13, 14, 20, 255))
    draw = ImageDraw.Draw(card)

    # Panel backgrounds
    # Left panel (chart area)
    draw.rounded_rectangle([20, 20, 560, H - 20], radius=16, fill=(20, 22, 30, 255))
    # Right panel (history)
    draw.rounded_rectangle([580, 20, W - 20, H - 20], radius=16, fill=(20, 22, 30, 255))

    # Avatar
    if avatar_img:
        card.paste(avatar_img, (36, 36), avatar_img)
    else:
        draw.ellipse([36, 36, 116, 116], fill=(40, 42, 55, 255))

    # Username text
    try:
        font_big = ImageFont.truetype("arial.ttf", 22)
        font_med = ImageFont.truetype("arial.ttf", 14)
        font_sm  = ImageFont.truetype("arial.ttf", 12)
        font_xs  = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font_big = ImageFont.load_default()
        font_med = font_big
        font_sm  = font_big
        font_xs  = font_big

    draw.text((128, 46), target.display_name, font=font_big, fill=(230, 230, 230, 255))
    draw.text((128, 74), f"@{target.name}", font=font_med, fill=(110, 115, 135, 255))

    # Big profit number
    draw.text((36, 128), f"{profit_sign}{profit_now:,.2f}", font=font_big, fill=(230, 230, 230, 255))
    profit_color_rgb = (0, 230, 118, 255) if is_positive else (255, 23, 68, 255)
    draw.text((36, 158), f"{profit_sign}{profit_now:,.2f}", font=font_sm, fill=profit_color_rgb)

    # --- Draw chart using matplotlib, render to PIL ---
    fig, ax = plt.subplots(figsize=(5.0, 2.2), dpi=100)
    fig.patch.set_facecolor("#14161E")
    ax.set_facecolor("#14161E")

    xs = list(range(len(profits)))
    ys = profits

    ax.plot(xs, ys, color=line_color, linewidth=2.0, solid_capstyle="round")
    ax.fill_between(xs, ys, min(ys) - abs(max(ys) - min(ys)) * 0.1,
                    color=fill_color, alpha=0.18)

    # Dot at last point
    ax.scatter([xs[-1]], [ys[-1]], color=line_color, s=50, zorder=5)

    ax.set_xlim(0, max(1, len(xs) - 1))
    ax.axis("off")
    fig.tight_layout(pad=0.2)

    chart_buf = io.BytesIO()
    fig.savefig(chart_buf, format="png", dpi=100, bbox_inches="tight",
                facecolor="#14161E", transparent=False)
    plt.close(fig)
    chart_buf.seek(0)
    chart_pil = PILImage.open(chart_buf).convert("RGBA")
    chart_pil = chart_pil.resize((500, 200))
    card.paste(chart_pil, (30, 185), chart_pil)

    # Profits badge
    draw.rounded_rectangle([36, H - 80, 200, H - 40], radius=20, fill=(30, 33, 45, 255))
    draw.text((56, H - 68), "Profits", font=font_xs, fill=(110, 115, 135, 255))
    draw.text((56, H - 52), f"{profit_sign}{profit_now:,.2f}", font=font_sm, fill=profit_color_rgb)

    # --- Right panel: deposit history ---
    rx = 596
    draw.text((rx, 36), "TYPE", font=font_xs, fill=(90, 95, 115, 255))
    draw.text((rx + 140, 36), "DATE", font=font_xs, fill=(90, 95, 115, 255))
    draw.text((rx + 240, 36), "AMOUNT", font=font_xs, fill=(90, 95, 115, 255))

    # Divider
    draw.line([(rx, 56), (W - 36, 56)], fill=(35, 38, 52, 255), width=1)

    if deposit_rows:
        for i, (dep_amt, dep_ts) in enumerate(deposit_rows[:6]):
            y = 66 + i * 44
            if y + 36 > H - 30:
                break
            row_bg = (24, 27, 38, 255) if i % 2 == 0 else (20, 22, 30, 255)
            draw.rounded_rectangle([rx - 8, y, W - 28, y + 36], radius=8, fill=row_bg)
            # Icon circle
            draw.ellipse([rx, y + 8, rx + 20, y + 28], fill=(30, 180, 80, 60))
            draw.text((rx + 4, y + 10), "↓", font=font_sm, fill=(0, 210, 90, 255))
            draw.text((rx + 28, y + 12), "Deposit", font=font_sm, fill=(200, 205, 220, 255))
            import datetime
            dt = datetime.datetime.fromtimestamp(dep_ts)
            draw.text((rx + 140, y + 6), dt.strftime("%Y/%m/%d"), font=font_xs, fill=(140, 145, 165, 255))
            draw.text((rx + 140, y + 20), dt.strftime("%I:%M %p"), font=font_xs, fill=(100, 105, 125, 255))
            draw.text((rx + 250, y + 12), f"{dep_amt:+,.2f}", font=font_sm,
                      fill=(0, 210, 90, 255) if dep_amt >= 0 else (255, 60, 60, 255))
    else:
        draw.text((rx, 80), "No deposits yet.", font=font_sm, fill=(100, 105, 125, 255))

    buf = io.BytesIO()
    card.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    return buf


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
