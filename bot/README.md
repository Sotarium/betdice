# Betdice Discord Bot (Railway)

## Deploy on Railway

1. New Project → Deploy from GitHub → select **Sotarium/betdice**
2. **Settings → Root Directory** = `bot`
3. **Settings → Start Command** = `python main.py`
4. **Variables** add:
   - `DISCORD_TOKEN` = your bot token
   - `SITE_URL` = `https://betdice.vercel.app` (optional)
5. Deploy

Do **not** use the whole repo root (that is the Next.js site).

## Local

```bash
cd bot
pip install -r requirements.txt
set DISCORD_TOKEN=your_token
python main.py
```
