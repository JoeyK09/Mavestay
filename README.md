# MaveStay Telegram Bot

A Telegram bot for browsing property listings and submitting booking inquiries —
built for MaveStay (under Mave Group).

## Features (v2)

- `/start` — main menu (Browse Listings, Favorites, My Inquiries, Contact Support, Language)
- **Multi-language**: English, Spanish, French, Portuguese, Arabic, Swahili, Chinese.
  Auto-detected from the user's Telegram client on first use, changeable anytime
  with `/language`.
- **Browse by country** — listings grouped by country, then city
- Each listing shows rating, review count, and "🔥 Popular" / "🆕 New" tags
- **❤️ Favorites** — save/unsave listings, view them anytime
- **Cross-platform links** — every listing has a "View on Airbnb" button
  (your referral link) and a "View on Booking.com" button (shows a
  "coming soon" message until you send me that link)
- Submit a booking inquiry (name, phone, check-in/out dates, guest count)
- Inquiries saved to a local SQLite database
- Optional: new inquiries get pushed to an admin chat/group instantly
- `/mybookings` — check status of your own inquiries anytime

Currently seeded with 14 sample listings across 14 countries (Nigeria, Kenya,
Ghana, Rwanda, South Africa, Spain, France, Portugal, UAE, Thailand,
Indonesia, USA, Brazil, Japan) so you can test the whole flow end-to-end
before adding real properties.

**Note:** property names/descriptions are stored in English only for now —
only the bot's menus and prompts are translated. Translating listing content
itself would need either per-language fields in the database or a live
translation API call.

## Payments (Crypto, PayPal, Airtm, M-Pesa)

After a guest submits a booking inquiry, they're shown 4 payment method
buttons. Tapping one shows your account details (wallet address, PayPal.me
link, Airtm handle, or M-Pesa paybill) plus a unique reference code, and an
"I've Paid" button.

**Important — this is a manual-verify flow, not live payment processing:**
none of these providers are wired up to auto-confirm via API. Here's the
actual flow:

1. Guest picks a method → sees your payment details + reference code
2. Guest sends payment outside the bot, then taps "✅ I've Paid"
3. You get notified in your admin chat with the booking + reference
4. You check that the payment actually arrived (your wallet, PayPal, etc.)
5. You run `/confirmpayment <booking_id>` in the bot to mark it confirmed —
   this also checks and rewards any referral milestone (see below)

Set up your payment details in `.env`:
```
CRYPTO_WALLETS=BTC:bc1qxyz...,USDT-TRC20:Txyz...
PAYPAL_ME_LINK=https://paypal.me/yourname
AIRTM_HANDLE=your_airtm_handle
MPESA_PAYBILL=123456
MPESA_ACCOUNT_NAME=MaveStay
```
Any method left blank shows guests a "coming soon" message instead.

**Going live later:** when you're ready for real-time automatic payment
confirmation instead of manual checking, the natural upgrades are
NOWPayments/Coinbase Commerce (crypto), PayPal Orders API (PayPal), and
Safaricom's Daraja STK Push API (M-Pesa) — each needs its own merchant
account and a webhook endpoint. Airtm requires a business/API agreement
with Airtm directly. Let me know when you're ready for any of these.

## Refer & Earn

Every user gets a unique referral link (`🎁 Refer & Earn` in the menu, or
`/referral`). When a friend joins through that link and their booking gets
marked `/confirmpayment`-confirmed, it counts as one successful referral.

Every **10 successful referrals** (configurable) earns the referrer
**$10** (configurable) — they get an automatic congrats message when they
hit the milestone.

Configure in `.env`:
```
REFERRAL_MILESTONE=10
REFERRAL_REWARD_AMOUNT=10
BOT_USERNAME=YourBotUsername
```
`BOT_USERNAME` (without the @) is required to generate working referral
links like `t.me/YourBotUsername?start=ref_abc123`.

**Note:** rewards are tracked and displayed automatically, but payout itself
is manual — you're responsible for actually sending referrers their earned
amount (e.g. via the same payment methods above). A `/referral` command
also exists for guests to check their own stats anytime.

## Setup

1. **Create your bot**
   Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` →
   follow the prompts → copy the token it gives you.

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and paste in your `BOT_TOKEN`.

   Optional: to get instant alerts when someone submits an inquiry, message
   [@userinfobot](https://t.me/userinfobot) to get your Telegram user ID, and
   set `ADMIN_CHAT_ID` in `.env`.

4. **Run it**
   ```bash
   python bot.py
   ```
   Open Telegram, find your bot, and send `/start`.

## Project structure

```
mavestay_bot/
├── bot.py            # Bot handlers & conversation flow
├── database.py        # SQLite schema, sample data, queries
├── locales.py          # UI translations for all supported languages
├── payments.py         # Payment method config & instruction builder
├── requirements.txt
├── .env.example
└── mavestay.db        # Created automatically on first run
```

## Adding real listings

Right now listings are seeded once in `database.py` (`seed_sample_properties`).
To add real properties, either:

- Edit the `sample` list in `database.py` and delete `mavestay.db` to reseed, or
- Insert directly, e.g.:
  ```python
  import database as db
  db.init_db()
  with db.get_conn() as conn:
      conn.execute(
          "INSERT INTO properties (name, location, price_per_night, bedrooms, description) "
          "VALUES (?, ?, ?, ?, ?)",
          ("New Property", "City, Country", 100.0, 2, "Description here")
      )
  ```

A simple `/addproperty` admin command or a small web form would be natural
next steps once you're ready to manage listings without touching code.

## Adding the Booking.com link

Once you have the link, put it in `.env`:
```
BOOKING_URL=https://your-booking-com-link-here
```
That's it — the button will automatically become a live link instead of the
"coming soon" alert.

## Next steps / roadmap ideas

- Photo support for listings (Telegram photo messages, not just text)
- Search/filter by location, price range, or dates
- Admin commands to approve/decline inquiries from within Telegram
- Move from SQLite to Postgres if this needs to scale or run on multiple servers
- Hook into MaveConnect later (referral credit for bookings, VIP perks) —
  kept fully separate for now per your setup

## Deployment

For 24/7 uptime you'll want to host this somewhere rather than running it on
your own machine — Railway, Render, or a small VPS all work well for a
polling-based bot like this. Let me know when you're ready and I can walk
through deployment options.
