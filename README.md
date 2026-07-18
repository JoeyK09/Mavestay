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

## How you actually earn money

Since MaveStay's listings are all third-party owned properties (not yours),
your income is **commission-based**, like a traditional booking platform:

1. Guest pays the **full booking amount** into your own accounts (crypto
   wallet, PayPal, Airtm, or M-Pesa — whichever they choose)
2. When you run `/confirmpayment <id>` (or tap Confirm from `/pending`),
   the bot automatically splits that payment:
   - **Your commission** (default 15%, set via `MAVESTAY_COMMISSION_RATE`,
     overridable per property if an owner negotiated a different rate)
   - **Owner payout** — the rest, which you remit to the property owner
     yourself (bank transfer, mobile money, whatever you've arranged with them)
3. The admin confirmation message shows you exactly both numbers, so you
   always know what to keep and what to send on

This is a **manual payout model** — money lands in your account first, and
you forward the owner's share yourself. A fully automatic split (where the
owner gets paid directly and instantly) needs a marketplace payment setup
like Stripe Connect, which is a bigger integration for later once volume
justifies it.

**Other ways to earn**, not built yet but worth considering as MaveStay
grows: charging property owners a fee for featured/"Popular" placement,
a paid VIP membership tier for guests (discounts, priority booking), or a
flat service fee added on top of the nightly rate. Happy to build any of
these when you're ready.

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

## Refer & Earn (designed to never dilute your income)

Every user gets a unique referral link (`🎁 Refer & Earn` in the menu, or
`/referral`). The reward is a **percentage of your own commission** on each
booking a referred friend completes — not a flat amount, and never a cut of
what's owed to the property owner.

**Example:** a friend books a $340 stay. Your commission at 15% is $51.
At the default 20% referral rate, the referrer earns **$10.20** on that one
booking — automatically calculated and credited to their balance the moment
you run `/confirmpayment`.

This means:
- Referral payouts scale exactly with your real revenue — you can never
  owe more than a fixed fraction of what you actually earned
- The property owner's payout is completely untouched by any of this
- Earnings accrue continuously (every confirmed referred booking adds to
  their balance), and every `REFERRAL_MILESTONE` (default 10) confirmed
  referred bookings, the referrer gets an automatic congrats message
  showing their running total

Guests can check their link, running balance, and confirmed-referral count
anytime via `/referral`.

Configure in `.env`:
```
MAVESTAY_COMMISSION_RATE=0.15
REFERRAL_REWARD_RATE=0.20
REFERRAL_MILESTONE=10
BOT_USERNAME=YourBotUsername
```
`BOT_USERNAME` (without the @) is required to generate working referral
links like `t.me/YourBotUsername?start=ref_abc123`.

**Note:** like owner payouts, referral rewards are tracked automatically
but paid out manually — you're responsible for actually sending referrers
their earned balance once you're ready (via the same payment methods above).

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
To add a real property, use the `add_property()` helper, which also lets you
record the owner's details and (optionally) a custom commission rate for them:

```python
import database as db
db.init_db()
db.add_property(
    name="Sunset Villa",
    city="Lagos", country="Nigeria",
    price_per_night=85.0, bedrooms=3,
    description="Cozy villa with a private pool.",
    owner_name="John Doe",
    owner_contact="+234...",
    owner_payout_method="M-Pesa till 123456",
    commission_rate=None,  # leave None to use your global MAVESTAY_COMMISSION_RATE
)
```

A simple `/addproperty` admin command or a small web form would be natural
next steps once you're ready to manage listings without touching code.

## Direct booking & real availability

Once a guest taps "✅ I've Paid," their dates lock automatically — the bot
checks for overlaps against every other booking that's pending confirmation
or already confirmed, and rejects the date range at the *inquiry* stage if
it's already taken. There's also a second check right when payment is
claimed, to catch the rare case where two guests were mid-booking for the
same dates at the same time — whoever pays first keeps the dates; the
second guest gets a clear message to contact support (and you get an admin
alert to help sort it out, including a refund if they already sent money).

Unpaid inquiries never block dates — only an actual payment claim does.
This means guests can browse and start an inquiry freely without
accidentally locking out other guests.

**A note on "pulling in listings from other platforms":** Airbnb and
Booking.com don't allow third-party sites to host their real inventory for
direct booking and payment collection — bookings there have to go through
their own checkout, for insurance/legal reasons, and scraping their
listings would violate their terms of service. The realistic options are:
- **Referral links** (already built in for Airbnb) — guest finishes the
  booking on Airbnb's own site/app, you earn a commission
- **Official affiliate/API partnership** — Booking.com's Affiliate Partner
  Program and Expedia's Rapid API let approved partners show live
  inventory, sometimes with revenue-share bookings — but this requires
  applying and being accepted by them directly

The direct-booking system above (real availability, instant date-locking)
works for **your own inventory** — properties you or partnered owners
actually list on MaveStay. That's the piece that scales as your real
property network grows.

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

### Render-specific note: Python version

Render defaults new services to the latest available Python (currently
3.14), but `python-telegram-bot`'s polling mode isn't compatible with how
3.13+ handles `asyncio.get_event_loop()` — you may see:
```
RuntimeError: There is no current event loop in thread 'MainThread'.
```
This repo includes a `runtime.txt` pinning Python to `3.11.9`, which Render
reads automatically — just make sure it's committed alongside the other
files. `bot.py` also has a small safety-net fix for this at startup, so it
should work even if a future Python bump reintroduces the issue.
