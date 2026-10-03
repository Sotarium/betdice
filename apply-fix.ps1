# Betdice Deposit Fix Script for Windows PowerShell
# Run this inside your betdice directory on any Windows machine:
# powershell -ExecutionPolicy Bypass -File .\apply-fix.ps1

$ErrorActionPreference = "Stop"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "         Betdice Deposit Auto-Fix Script             " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Locate target directory
$currentPath = (Get-Location).Path
if (Test-Path "$currentPath\app\api\plisio\callback\route.ts") {
    $targetDir = $currentPath
} elseif (Test-Path "$currentPath\betdice\app\api\plisio\callback\route.ts") {
    $targetDir = "$currentPath\betdice"
} else {
    Write-Host "Error: Could not find betdice directory structure." -ForegroundColor Red
    Write-Host "Please place and run this script inside the betdice folder." -ForegroundColor Yellow
    Exit 1
}

Write-Host "[+] Found repository at: $targetDir" -ForegroundColor Green

# 1. Patch app/api/plisio/callback/route.ts
$callbackFile = "$targetDir\app\api\plisio\callback\route.ts"
$callbackContent = Get-Content $callbackFile -Raw

if ($callbackContent -notmatch "deposit-credit") {
    $targetBlock = @'
    if (data.status === "completed" && (data.ipn_type === "pay_in" || data.ipn_type === "invoice")) {
      const uid = data.deposit_uid || data.order_number;
      const amount = parseFloat(data.source_amount || data.amount || "0");
      console.log(`→ Credit user ${uid} with ${amount}`);
    }
'@

    $replacementBlock = @'
    if (data.status === "completed" && (data.ipn_type === "pay_in" || data.ipn_type === "invoice")) {
      const uid = data.deposit_uid || data.order_number;
      const amount = parseFloat(data.source_amount || data.amount || "0");
      console.log(`→ Credit user ${uid} with ${amount}`);

      const botUrl = process.env.BOT_INTERNAL_URL || process.env.BOT_URL;
      const botSecret = process.env.BOT_INTERNAL_SECRET || "betdice_secret";

      if (botUrl && uid) {
        try {
          const forwardRes = await fetch(`${botUrl.replace(/\/$/, "")}/deposit-credit`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${botSecret}`,
            },
            body: JSON.stringify({
              discordId: String(uid),
              amount: amount,
              currency: data.currency || data.psys_cid || "CRYPTO",
              txid: data.txn_id || data.tx_url || "",
            }),
          });
          const resData = await forwardRes.json().catch(() => ({}));
          console.log("[Bot forward response]", forwardRes.status, resData);
        } catch (botErr) {
          console.error("[Bot forward error] Failed to reach bot listener:", botErr);
        }
      }
    }
'@

    $callbackContent = $callbackContent.Replace($targetBlock, $replacementBlock)
    Set-Content -Path $callbackFile -Value $callbackContent -NoNewline
    Write-Host "[OK] Patched app/api/plisio/callback/route.ts" -ForegroundColor Green
} else {
    Write-Host "[i] app/api/plisio/callback/route.ts already patched." -ForegroundColor Yellow
}

# 2. Patch bot/main.py
$botFile = "$targetDir\bot\main.py"
$botContent = Get-Content $botFile -Raw

if ($botContent -notmatch "handle_deposit_credit") {
    $oldImport = "import io"
    $newImport = "import io`r`nimport asyncio`r`nfrom aiohttp import web"
    $botContent = $botContent.Replace($oldImport, $newImport)

    $oldSite = "SITE_URL = os.getenv(`r`n    `"SITE_URL`",`r`n    `"https://betdice-frouxzys-projects-fcc3f71b.vercel.app`",`r`n)"
    $newSite = "SITE_URL = os.getenv(`r`n    `"SITE_URL`",`r`n    `"https://betdice-frouxzys-projects-fcc3f71b.vercel.app`",`r`n)`r`nBOT_INTERNAL_SECRET = os.getenv(`"BOT_INTERNAL_SECRET`", `"betdice_secret`")`r`nBOT_PORT = int(os.getenv(`"PORT`", os.getenv(`"BOT_PORT`", `"8080`")))"
    $botContent = $botContent.Replace($oldSite, $newSite)

    $targetBal = "def add_balance(uid: int, amount: float):`r`n    get_user(uid)`r`n    db.execute(`"UPDATE users SET balance = balance + ? WHERE id=?`", (amount, uid))`r`n    db.commit()"
    $webhookFuncs = @'
def add_balance(uid: int, amount: float):
    get_user(uid)
    db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    db.commit()


async def notify_user_deposit(discord_id: int, amount: float, new_balance: float):
    try:
        user = await bot.fetch_user(discord_id)
        if user:
            embed = discord.Embed(
                title="Deposit Credited! 🎲",
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
'@
    $botContent = $botContent.Replace($targetBal, $webhookFuncs)

    $oldRunner = "if __name__ == `"__main__`":`r`n    token = os.getenv(`"DISCORD_TOKEN`")`r`n    if not token:`r`n        raise SystemExit(`"Set DISCORD_TOKEN environment variable`")`r`n    bot.run(token)"
    $newRunner = "async def run_bot_and_server():`r`n    token = os.getenv(`"DISCORD_TOKEN`")`r`n    if not token:`r`n        raise SystemExit(`"Set DISCORD_TOKEN environment variable`")`r`n    await start_http_server()`r`n    await bot.start(token)`r`n`r`n`r`nif __name__ == `"__main__`":`r`n    asyncio.run(run_bot_and_server())"
    $botContent = $botContent.Replace($oldRunner, $newRunner)

    Set-Content -Path $botFile -Value $botContent -NoNewline
    Write-Host "[OK] Patched bot/main.py" -ForegroundColor Green
} else {
    Write-Host "[i] bot/main.py already patched." -ForegroundColor Yellow
}

# 3. Create .env.example
$envFile = "$targetDir\.env.example"
$envLines = @'
# ========================================================
# 1. Environment variables for Vercel (Next.js App)
# ========================================================
PLISIO_SECRET_KEY=your_plisio_secret_key_here
NEXT_PUBLIC_SITE_URL=https://your-domain.vercel.app

# URL where the Discord bot is reachable (e.g. https://your-bot.up.railway.app or http://vps-ip:8080 or ngrok)
BOT_INTERNAL_URL=http://YOUR_BOT_HOST_OR_IP:8080
BOT_INTERNAL_SECRET=choose_a_strong_shared_secret_here

# ========================================================
# 2. Environment variables for the Discord Bot host
# ========================================================
DISCORD_TOKEN=your_discord_bot_token
SITE_URL=https://your-domain.vercel.app
BOT_PORT=8080
BOT_INTERNAL_SECRET=choose_a_strong_shared_secret_here
'@
Set-Content -Path $envFile -Value $envLines -NoNewline
Write-Host "[OK] Created .env.example" -ForegroundColor Green

Write-Host "`nAll fixes applied successfully!" -ForegroundColor Green
