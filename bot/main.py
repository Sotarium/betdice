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
    if interaction.command and interaction.command.name == "setup":
        return True
    if getattr(interaction.channel, "category_id", None) == ALLOWED_CATEGORY_ID:
        return True
    await interaction.response.send_message(
        "You can't use this command here. Use it in the play channels.",
        ephemeral=True,
    )
    return False


bot.tree.interaction_check = category_check


@bot.tree.command(name="setup", description="Create the server categories and channels")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    created = []
    everyone = guild.default_role
    for cat_name, channels in LAYOUT.items():
        category = discord.utils.get(guild.categories, name=cat_name)
        if category is None:
            category = await guild.create_category(cat_name)
            created.append(f"category: {cat_name}")
        await category.set_permissions(everyone, overwrite=everyone_overwrite())
        for ch_name, read_only in channels:
            channel = discord.utils.get(category.text_channels, name=ch_name.lower())
            if channel is None:
                channel = await guild.create_text_channel(ch_name, category=category)
                created.append(f"channel: {ch_name}")
            await channel.set_permissions(everyone, overwrite=everyone_overwrite(read_only))
            created.append(f"permissions set: {ch_name}")
    msg = "Done:\n" + "\n".join(created)
    await interaction.followup.send(msg, ephemeral=True)


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
    "id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, last_daily REAL DEFAULT 0)"
)
db.commit()

DAILY_AMOUNT = 100.0
DAILY_COOLDOWN = 24 * 60 * 60


def get_user(uid: int):
    row = db.execute("SELECT balance, last_daily FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        db.execute("INSERT INTO users (id) VALUES (?)", (uid,))
        db.commit()
        return 0.0, 0.0
    return row


def add_balance(uid: int, amount: float):
    get_user(uid)
    db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    db.commit()


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

        add_balance(discord_id, amount)
        new_balance, _ = get_user(discord_id)
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

        if status == 200 and (data.get("addresses") or data.get("address")):
            try:
                await session.post(
                    f"{SITE_URL}/api/users/sync",
                    json={
                        "discordId": str(discord_id),
                        "username": username,
                        "avatar": avatar_hash,
                        "type": "Deposit",
                        "amount": 0,
                        "balance": get_user(discord_id)[0],
                        "profit": 0,
                        "label": "address_issued",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                )
            except Exception:
                pass

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

        bal, _ = get_user(interaction.user.id)
        if amt > bal:
            await interaction.response.send_message(
                f"Not enough balance. You have **{bal:,.2f}** dices.",
                ephemeral=True,
            )
            return

        add_balance(interaction.user.id, -amt)

        import aiohttp
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

        embed = discord.Embed(
            title="Withdraw requested",
            description=(
                f"**Amount:** {amt:,.2f} dices\n"
                f"**Address:** `{self.address.value}`\n\n"
                "Balance deducted. Payout will be processed."
            ),
            color=0x2B2D31,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
    balance, _ = get_user(target.id)
    title = "Your balance" if target == interaction.user else f"{target.display_name}'s balance"

    embed = discord.Embed(
        title=title,
        description=f"{dice_emoji(interaction.guild)} **{balance:,.2f}** dices",
        color=0x2B2D31,
    )

    if target == interaction.user:
        view = BalanceView(target.id)
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="daily", description="Claim your free daily dice")
async def daily(interaction: discord.Interaction):
    uid = interaction.user.id
    _, last = get_user(uid)
    now = time.time()
    if now - last < DAILY_COOLDOWN:
        left = int(DAILY_COOLDOWN - (now - last))
        h, m = left // 3600, (left % 3600) // 60
        await interaction.response.send_message(
            f"Come back in {h}h {m}m for your next daily.", ephemeral=True
        )
        return
    add_balance(uid, DAILY_AMOUNT)
    db.execute("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    db.commit()
    await interaction.response.send_message(
        f"You claimed {dice_emoji(interaction.guild)} {DAILY_AMOUNT:,.2f} dices!"
    )


@bot.tree.command(name="credit", description="[Admin] Manually credit a user's dice balance")
@app_commands.describe(
    user="The Discord user to credit",
    amount="Amount of dices to add",
    user_id="Optional: Enter Discord User ID directly if user is not in server"
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def credit(
    interaction: discord.Interaction,
    amount: float,
    user: discord.Member = None,
    user_id: str = None,
):
    target_id = None
    target_name = "User"
    if user:
        target_id = user.id
        target_name = user.display_name
    elif user_id:
        try:
            target_id = int(user_id.strip())
            target_name = f"<@{target_id}>"
        except ValueError:
            await interaction.response.send_message("Invalid user_id.", ephemeral=True)
            return
    else:
        await interaction.response.send_message("Please provide either a user mention or a user_id.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    add_balance(target_id, amount)
    new_bal, _ = get_user(target_id)

    asyncio.create_task(notify_user_deposit(target_id, amount, new_bal))
    asyncio.create_task(sync_website_deposit(target_id, amount, new_bal))

    embed = discord.Embed(
        title="Admin Credit Added 🎲",
        description=f"Credited **+{amount:,.2f}** dices to **{target_name}** (`{target_id}`).\nNew Balance: **{new_bal:,.2f}** dices.",
        color=0x2B2D31,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


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

    balance, _ = get_user(interaction.user.id)
    if amount > balance:
        await interaction.response.send_message(
            f"Not enough balance. You have **{balance:,.2f}** dices.",
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
    amount="Amount of dices to tip"
)
async def tip(interaction: discord.Interaction, user: discord.Member, amount: float):
    if interaction.user.id != ALLOWED_TIPPER_ID:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("You cannot tip yourself.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
        return

    sender_bal, _ = get_user(interaction.user.id)
    if amount > sender_bal:
        await interaction.response.send_message(
            f"Not enough balance. You have **{sender_bal:,.2f}** dices.",
            ephemeral=True,
        )
        return

    # Deduct from tipper and add to recipient
    add_balance(interaction.user.id, -amount)
    add_balance(user.id, amount)

    sender_new, _ = get_user(interaction.user.id)
    recipient_new, _ = get_user(user.id)

    # Send DM to the recipient: "User" Tipped You X! \n Your new balance: Y
    try:
        embed = discord.Embed(
            title=f"\"{interaction.user.display_name}\" Tipped You {amount:,.2f}!",
            description=f"Your new balance: **{recipient_new:,.2f}** dices",
            color=0x2B2D31,
        )
        await user.send(embed=embed)
    except Exception as e:
        print(f"[Tip DM Error] Could not DM user {user.id}: {e}")

    # Confirm in channel
    confirm_embed = discord.Embed(
        title="Tip Sent!",
        description=f"Successfully tipped **{amount:,.2f}** dices to {user.mention}.\nYour remaining balance: **{sender_new:,.2f}** dices.",
        color=0x2B2D31,
    )
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


async def run_bot_and_server():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable")
    await start_http_server()
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(run_bot_and_server())
