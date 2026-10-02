# Betdice API

Backend only — provably fair generation + Plisio webhooks for the Discord bot.
**No games are hosted on this website.**

## Public URL
https://betdice.vercel.app

## API Endpoints

### 1. Get a new server seed (before a game)
```
GET /api/fair/seed
```
Returns:
```json
{
  "roll_id": "...",
  "server_seed_hash": "...",
  "server_seed": "..."
}
```
Show `server_seed_hash` to the user in Discord before they bet.

### 2. Roll (bot calls this to get the result)
```
POST /api/fair/roll
Content-Type: application/json

{
  "server_seed": "...",
  "client_seed": "user_seed_or_random",
  "nonce": 0,
  "target": 50,
  "direction": "under"
}
```
Returns the float 0–100 + win/lose if target/direction given.

### 3. Verify a past roll (public)
```
POST /api/fair/verify
{
  "server_seed": "...",
  "client_seed": "...",
  "nonce": 0,
  "claimed_result": 42.17
}
```

### 4. Plisio deposit webhook
```
POST /api/plisio/callback?json=true
```
Set this URL in Plisio → API settings → Status URL.

## Environment variables (Vercel)

| Key | Value |
|-----|-------|
| `PLISIO_SECRET_KEY` | Your Plisio secret key (type: Secret) |
| `NEXT_PUBLIC_SITE_URL` | `https://betdice.vercel.app` (type: Config is fine) |

**Do NOT put the Plisio key in `NEXT_PUBLIC_SITE_URL`.**

## Discord bot usage example

```python
import aiohttp

async def get_fair_roll(client_seed: str, nonce: int, target: float, direction: str):
    async with aiohttp.ClientSession() as session:
        # 1. get seed
        async with session.get("https://betdice.vercel.app/api/fair/seed") as r:
            seed_data = await r.json()

        # 2. roll
        async with session.post("https://betdice.vercel.app/api/fair/roll", json={
            "server_seed": seed_data["server_seed"],
            "client_seed": client_seed,
            "nonce": nonce,
            "target": target,
            "direction": direction,
        }) as r:
            return await r.json()
```
