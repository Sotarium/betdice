# Betdice

Provably fair dice games + crypto deposits (Plisio) for Discord community.

## Features

- **Provably Fair Dice** – Server seed + Client seed + Nonce. Verify every roll yourself.
- **Balance system** – Deposit / Withdraw buttons
- **Plisio ready** – Unique deposit addresses + webhook endpoint
- Dark UI matching Discord style

## Quick Start (local)

```bash
npm install
npm run dev
```

Open http://localhost:3000

## Environment variables (Vercel / .env.local)

```
PLISIO_SECRET_KEY=your_plisio_secret_key
NEXT_PUBLIC_SITE_URL=https://your-domain.vercel.app
```

## Plisio Setup

1. Get Secret Key from Plisio → API → API settings
2. Set **Status URL** to:
   `https://your-domain.vercel.app/api/plisio/callback?json=true`
3. Use coin `USDT_TRX` (recommended) or others

## Deploy to Vercel

Already linked via GitHub. Just push to `main` and Vercel auto-deploys.

## Discord Bot Sync

Balances are stored per Discord user ID. Connect Discord OAuth later or keep the bot writing to the same database.
