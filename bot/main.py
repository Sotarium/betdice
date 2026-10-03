"""
Betdice Discord bot
Requires env: DISCORD_TOKEN
Optional: SITE_URL
"""
import os
import discord
from discord import app_commands
import sqlite3
import time
import io

SITE_URL = os.getenv(
    "SITE_URL",
    "https://betdice-frouxzys-projects-fcc3f71b.vercel.app",
)

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


async def get_deposit_address(discord_id: int, username: str, avatar_hash):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SITE_URL}/api/plisio/deposit",
            json={"discordId": str(discord_id)},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            text = await r.text()
            status = r.status
            try:
                data = await r.json(content_type=None)
            except Exception:
                data = {"error": text[:300]}

        if status == 200 and data.get("address"):
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
        label="Your Solana wallet address",
        placeholder="Paste your SOL address",
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
                f"**Solana address:** `{self.address.value}`\n\n"
                "Balance deducted. SOL payout will be processed."
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

        if status != 200 or not data.get("address"):
            err = data.get("error", str(data)[:200])
            await interaction.followup.send(
                f"Could not get deposit address.\n`{err}`\n\n"
                "On Plisio:\n"
                "• Enable **White-label**\n"
                "• Create/enable **SOL (Solana)** wallet\n"
                "• Set PLISIO_SECRET_KEY on Vercel",
                ephemeral=True,
            )
            return

        address = data["address"]

        embed = discord.Embed(
            title="Deposit SOL (Solana)",
            description=(
                f"Send **any amount of SOL** to this address:\n\n"
                f"```{address}```\n\n"
                f"**Network: Solana only**\n"
                f"This address is yours permanently.\n"
                f"Balance updates after Plisio confirms."
            ),
            color=0x2B2D31,
        )
        embed.set_footer(text="SOL · unique Solana address for your account")
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


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable")
    bot.run(token)
