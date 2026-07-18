"""
MaveStay Telegram Bot — Payment methods.

IMPORTANT — read this before going live:
This bot does NOT process payments automatically. None of these providers
(crypto, PayPal, Airtm, M-Pesa) have been wired up to verify payment via API
— that requires your actual merchant/API credentials, which only you can set
up. What this module DOES do:

  1. Show the guest your payment details (wallet address, PayPal.me link,
     Airtm handle, M-Pesa till/paybill) once they pick a method.
  2. Let the guest tap "I've Paid" to flag the booking as awaiting
     confirmation.
  3. You (the admin) verify the payment arrived on your end, then run
     /confirmpayment <booking_id> in the bot to mark it confirmed — this
     also triggers referral reward tracking.

This "manual verify" flow is standard for small operations and avoids
needing a live payment gateway integration right away. When you're ready
for real-time automatic confirmation, the natural upgrades are:
  - Crypto: NOWPayments or Coinbase Commerce API (webhook on payment)
  - PayPal: PayPal Orders API v2 (create + capture order, webhook)
  - M-Pesa: Safaricom Daraja STK Push API (webhook/callback URL)
  - Airtm: requires an Airtm business/merchant account and API agreement
Ask me when you're ready for any of these and I'll wire up the real API.
"""

import os

# ---------- Configure your payment details here (or via .env) ----------

# Comma-separated "LABEL:address" pairs, e.g. "BTC:bc1q...,USDT-TRC20:T9y..."
CRYPTO_WALLETS_RAW = os.getenv("CRYPTO_WALLETS", "")

PAYPAL_ME_LINK = os.getenv("PAYPAL_ME_LINK", "")  # e.g. https://paypal.me/yourname
AIRTM_HANDLE = os.getenv("AIRTM_HANDLE", "")  # your Airtm username/email
MPESA_PAYBILL = os.getenv("MPESA_PAYBILL", "")  # or till number
MPESA_ACCOUNT_NAME = os.getenv("MPESA_ACCOUNT_NAME", "")


def _parse_crypto_wallets():
    wallets = {}
    if not CRYPTO_WALLETS_RAW:
        return wallets
    for pair in CRYPTO_WALLETS_RAW.split(","):
        if ":" in pair:
            label, address = pair.split(":", 1)
            wallets[label.strip()] = address.strip()
    return wallets


CRYPTO_WALLETS = _parse_crypto_wallets()

METHODS = ["crypto", "paypal", "airtm", "mpesa"]


def is_configured(method: str) -> bool:
    if method == "crypto":
        return bool(CRYPTO_WALLETS)
    if method == "paypal":
        return bool(PAYPAL_ME_LINK)
    if method == "airtm":
        return bool(AIRTM_HANDLE)
    if method == "mpesa":
        return bool(MPESA_PAYBILL)
    return False


def build_details_block(method: str, reference: str) -> str:
    """Returns the raw payment details block (not translated — account
    numbers/addresses are the same regardless of the guest's language)."""
    if method == "crypto":
        if not CRYPTO_WALLETS:
            return ""
        lines = [f"{label}: `{addr}`" for label, addr in CRYPTO_WALLETS.items()]
        return "\n".join(lines) + f"\n\nReference (include in memo if possible): `{reference}`"

    if method == "paypal":
        if not PAYPAL_ME_LINK:
            return ""
        return f"{PAYPAL_ME_LINK}\n\nReference: `{reference}`\n(Add the reference in the payment note.)"

    if method == "airtm":
        if not AIRTM_HANDLE:
            return ""
        return f"Airtm handle: `{AIRTM_HANDLE}`\n\nReference: `{reference}`"

    if method == "mpesa":
        if not MPESA_PAYBILL:
            return ""
        name_line = f"\nAccount Name: {MPESA_ACCOUNT_NAME}" if MPESA_ACCOUNT_NAME else ""
        return f"Paybill/Till: `{MPESA_PAYBILL}`{name_line}\nAccount Number: `{reference}`"

    return ""
