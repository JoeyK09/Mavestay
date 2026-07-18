"""
MaveStay Telegram Bot — Property listings & booking inquiries
Multi-language, multi-country, with Airbnb/Booking.com cross-links.

Setup:
1. pip install -r requirements.txt
2. Copy .env.example to .env and fill in BOT_TOKEN (and optionally
   ADMIN_CHAT_ID, AIRBNB_URL, BOOKING_URL)
3. python bot.py

Get a BOT_TOKEN from @BotFather on Telegram.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
import payments
from locales import LANGUAGES, DEFAULT_LANG, t

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # optional, for booking alerts

# Airbnb referral link — used as a cross-link on every listing.
AIRBNB_URL = os.getenv(
    "AIRBNB_URL",
    "https://www.airbnb.com/rp/josephg120359?p=service&s=76&unique_share_id=9c268621-9d60-4cb1-b9c0-ec7492b7002c",
)
# Booking.com link — not provided yet. Leave BOOKING_URL unset in .env until
# you have it; the button will show a "coming soon" alert until then.
BOOKING_URL = os.getenv("BOOKING_URL", "")

# Refer & Earn: every N successful (paid & confirmed) referrals earns a reward.
REFERRAL_MILESTONE = int(os.getenv("REFERRAL_MILESTONE", "10"))
REFERRAL_REWARD_AMOUNT = float(os.getenv("REFERRAL_REWARD_AMOUNT", "10"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "")  # e.g. MaveStayBot, without @

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation states
NAME, PHONE, CHECKIN, CHECKOUT, GUESTS = range(5)


def lang_for(update: Update) -> str:
    user_id = update.effective_user.id
    return db.get_user_language(user_id, fallback=DEFAULT_LANG)


# ---------- Language selection ----------

def language_keyboard(prefix="setlang"):
    buttons = [
        InlineKeyboardButton(label, callback_data=f"{prefix}_{code}")
        for code, label in LANGUAGES.items()
    ]
    # 2 per row
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new_user = not db.user_exists(user.id)

    if is_new_user:
        # First time seeing this user — detect Telegram client language,
        # default to English if unsupported, then ask them to confirm.
        detected = (user.language_code or "")[:2]
        default = detected if detected in LANGUAGES else DEFAULT_LANG
        db.set_user_language(user.id, default)

        # Handle referral deep link: t.me/YourBot?start=ref_<code>
        if context.args:
            payload = context.args[0]
            if payload.startswith("ref_"):
                referrer_id = db.get_user_id_by_referral_code(payload[4:])
                if referrer_id:
                    db.set_referred_by(user.id, referrer_id)

        await update.message.reply_text(
            t(default, "choose_language"), reply_markup=language_keyboard()
        )
        return

    await show_main_menu(update, context)


async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_")[1]
    db.set_user_language(query.from_user.id, lang_code)
    await query.edit_message_text(t(lang_code, "language_updated"))
    await show_main_menu(update, context, edit=False, send_new=True)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    await update.message.reply_text(
        t(lang, "choose_language"), reply_markup=language_keyboard()
    )


# ---------- Main menu ----------

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          edit=True, send_new=False):
    lang = lang_for(update)
    keyboard = [
        [InlineKeyboardButton(t(lang, "menu_browse"), callback_data="browse")],
        [InlineKeyboardButton(t(lang, "menu_favorites"), callback_data="favorites")],
        [InlineKeyboardButton(t(lang, "menu_bookings"), callback_data="my_bookings")],
        [InlineKeyboardButton(t(lang, "menu_referral"), callback_data="referral")],
        [InlineKeyboardButton(t(lang, "menu_contact"), callback_data="contact")],
        [InlineKeyboardButton(t(lang, "menu_language"), callback_data="change_language")],
    ]
    text = t(lang, "welcome")
    markup = InlineKeyboardMarkup(keyboard)

    if update.message and not send_new:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    elif update.callback_query and edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")


async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)

    if query.data == "browse":
        await browse_countries(update, context)
    elif query.data == "favorites":
        await show_favorites(update, context)
    elif query.data == "my_bookings":
        await my_bookings(update, context)
    elif query.data == "referral":
        await show_referral(update, context)
    elif query.data == "contact":
        keyboard = [[InlineKeyboardButton(t(lang, "back_to_menu"), callback_data="back_to_menu")]]
        await query.edit_message_text(
            t(lang, "contact_text"), reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "change_language":
        await query.edit_message_text(
            t(lang, "choose_language"), reply_markup=language_keyboard()
        )
    elif query.data == "back_to_menu":
        await show_main_menu(update, context)


# ---------- Browse: countries -> listings ----------

async def browse_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    countries = db.get_countries()
    if not countries:
        await update.callback_query.edit_message_text(t(lang, "no_listings"))
        return

    keyboard = [
        [InlineKeyboardButton(country, callback_data=f"country_{country}")]
        for country in countries
    ]
    keyboard.append([InlineKeyboardButton(t(lang, "back_to_menu"), callback_data="back_to_menu")])

    await update.callback_query.edit_message_text(
        t(lang, "browse_header"), reply_markup=InlineKeyboardMarkup(keyboard)
    )


def _tag_label(lang, tag):
    if tag == "popular":
        return " " + t(lang, "tag_popular")
    if tag == "new":
        return " " + t(lang, "tag_new")
    return ""


async def list_country_properties(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)
    country = query.data.split("_", 1)[1]
    properties = db.get_properties_by_country(country)

    if not properties:
        await query.edit_message_text(t(lang, "no_listings"))
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{p['name']} — ${p['price_per_night']:.0f}{t(lang, 'per_night')}"
            f"{_tag_label(lang, p['tag'])}",
            callback_data=f"view_{p['id']}",
        )]
        for p in properties
    ]
    keyboard.append([InlineKeyboardButton(t(lang, "back_to_countries"), callback_data="browse")])

    await query.edit_message_text(
        t(lang, "listings_in", country=country),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def view_property(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)
    property_id = int(query.data.split("_")[1])
    p = db.get_property(property_id)

    if not p:
        await query.edit_message_text(t(lang, "no_listings"))
        return

    tag_line = _tag_label(lang, p["tag"]).strip()
    tag_line = f"{tag_line}\n" if tag_line else ""

    text = (
        f"*{p['name']}*{(' ' + tag_line) if tag_line else ''}\n"
        f"{t(lang, 'property_location')}: {p['city']}, {p['country']}\n"
        f"{t(lang, 'property_bedrooms')}: {p['bedrooms']}\n"
        f"{t(lang, 'property_price')}: ${p['price_per_night']:.0f}{t(lang, 'per_night')}\n"
        f"{t(lang, 'property_rating')}: {p['rating']:.1f} ({p['review_count']} {t(lang, 'reviews')})\n\n"
        f"{p['description']}"
    )

    is_fav = db.is_favorite(query.from_user.id, property_id)
    fav_label = t(lang, "favorite_remove") if is_fav else t(lang, "favorite_add")

    keyboard = [
        [InlineKeyboardButton(t(lang, "inquire_button"), callback_data=f"inquire_{p['id']}")],
        [InlineKeyboardButton(fav_label, callback_data=f"fav_{p['id']}")],
        [
            InlineKeyboardButton(t(lang, "airbnb_button"), url=AIRBNB_URL),
            InlineKeyboardButton(t(lang, "booking_button"), callback_data=f"booking_{p['id']}")
            if not BOOKING_URL else InlineKeyboardButton(t(lang, "booking_button"), url=BOOKING_URL),
        ],
        [InlineKeyboardButton(t(lang, "back_to_listings"), callback_data=f"country_{p['country']}")],
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def booking_com_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = lang_for(update)
    await query.answer(t(lang, "booking_coming_soon"), show_alert=True)


# ---------- Favorites ----------

async def toggle_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = lang_for(update)
    property_id = int(query.data.split("_")[1])
    user_id = query.from_user.id

    if db.is_favorite(user_id, property_id):
        db.remove_favorite(user_id, property_id)
        await query.answer(t(lang, "favorite_removed"))
    else:
        db.add_favorite(user_id, property_id)
        await query.answer(t(lang, "favorite_added"))

    # Refresh the property view so the button label updates
    await view_property(update, context)


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    user_id = update.callback_query.from_user.id
    favorites = db.get_favorites(user_id)

    keyboard = []
    if not favorites:
        text = t(lang, "favorites_empty")
    else:
        text = t(lang, "favorites_header")
        keyboard = [
            [InlineKeyboardButton(
                f"{p['name']} — {p['city']}, {p['country']}",
                callback_data=f"view_{p['id']}",
            )]
            for p in favorites
        ]
    keyboard.append([InlineKeyboardButton(t(lang, "back_to_menu"), callback_data="back_to_menu")])

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ---------- Refer & Earn ----------

def _referral_link(user_id: int) -> str:
    code = db.get_referral_code(user_id)
    if BOT_USERNAME:
        return f"https://t.me/{BOT_USERNAME}?start=ref_{code}"
    return f"(set BOT_USERNAME in .env to generate a shareable link) — your code: {code}"


async def _send_referral_text(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               lang: str, user_id: int, edit: bool):
    count = db.count_successful_referrals(user_id)
    earned = (count // REFERRAL_MILESTONE) * REFERRAL_REWARD_AMOUNT
    link = _referral_link(user_id)

    text = (
        f"{t(lang, 'referral_header')}\n\n"
        f"{t(lang, 'referral_link_label')}:\n{link}\n\n"
        f"{t(lang, 'referral_progress', count=count, milestone=REFERRAL_MILESTONE)}\n"
        f"{t(lang, 'referral_earned', amount=f'{earned:.0f}')}\n\n"
        f"{t(lang, 'referral_share_hint')}"
    )
    keyboard = [[InlineKeyboardButton(t(lang, "back_to_menu"), callback_data="back_to_menu")]]
    markup = InlineKeyboardMarkup(keyboard)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    user_id = update.callback_query.from_user.id
    await _send_referral_text(update, context, lang, user_id, edit=True)


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    user_id = update.message.from_user.id
    await _send_referral_text(update, context, lang, user_id, edit=False)


# ---------- My bookings ----------

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    user_id = update.callback_query.from_user.id
    bookings = db.get_bookings_for_user(user_id)

    if not bookings:
        text = t(lang, "mybookings_empty")
    else:
        lines = [t(lang, "mybookings_header") + "\n"]
        for b in bookings:
            lines.append(
                f"• {b['property_name']} ({b['city']}, {b['country']})\n"
                f"  {b['check_in']} → {b['check_out']}, {b['guests']} — _{b['status']}_"
            )
        text = "\n".join(lines)

    keyboard = [[InlineKeyboardButton(t(lang, "back_to_menu"), callback_data="back_to_menu")]]
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ---------- Booking inquiry conversation ----------

async def inquire_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)
    property_id = int(query.data.split("_")[1])
    context.user_data["inquiry"] = {"property_id": property_id}

    await query.edit_message_text(t(lang, "inquiry_ask_name"))
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    context.user_data["inquiry"]["guest_name"] = update.message.text
    await update.message.reply_text(t(lang, "inquiry_ask_phone"))
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    context.user_data["inquiry"]["phone"] = update.message.text
    await update.message.reply_text(t(lang, "inquiry_ask_checkin"))
    return CHECKIN


async def get_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    context.user_data["inquiry"]["check_in"] = update.message.text
    await update.message.reply_text(t(lang, "inquiry_ask_checkout"))
    return CHECKOUT


async def get_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    context.user_data["inquiry"]["check_out"] = update.message.text
    await update.message.reply_text(t(lang, "inquiry_ask_guests"))
    return GUESTS


def _compute_total(price_per_night: float, check_in: str, check_out: str):
    """Best-effort nights calculation if dates are valid ISO (YYYY-MM-DD).
    Returns None if they can't be parsed — guest still gets a per-night
    price on the listing page either way."""
    try:
        from datetime import date
        d1 = date.fromisoformat(check_in.strip())
        d2 = date.fromisoformat(check_out.strip())
        nights = (d2 - d1).days
        if nights > 0:
            return round(price_per_night * nights, 2)
    except (ValueError, TypeError):
        pass
    return None


async def get_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    inquiry = context.user_data["inquiry"]
    try:
        guests = int(update.message.text)
    except ValueError:
        await update.message.reply_text(t(lang, "inquiry_guests_invalid"))
        return GUESTS
    inquiry["guests"] = guests

    user = update.message.from_user
    p = db.get_property(inquiry["property_id"])
    total = _compute_total(p["price_per_night"], inquiry["check_in"], inquiry["check_out"])

    booking_id = db.create_booking(
        property_id=inquiry["property_id"],
        telegram_user_id=user.id,
        telegram_username=user.username or "",
        guest_name=inquiry["guest_name"],
        phone=inquiry["phone"],
        check_in=inquiry["check_in"],
        check_out=inquiry["check_out"],
        guests=guests,
        total_amount=total,
    )

    await update.message.reply_text(
        t(lang, "inquiry_success", name=p["name"], phone=inquiry["phone"]),
        parse_mode="Markdown",
    )

    # Offer payment methods right away
    keyboard = [
        [
            InlineKeyboardButton(t(lang, "pay_crypto"), callback_data=f"pay_crypto_{booking_id}"),
            InlineKeyboardButton(t(lang, "pay_paypal"), callback_data=f"pay_paypal_{booking_id}"),
        ],
        [
            InlineKeyboardButton(t(lang, "pay_airtm"), callback_data=f"pay_airtm_{booking_id}"),
            InlineKeyboardButton(t(lang, "pay_mpesa"), callback_data=f"pay_mpesa_{booking_id}"),
        ],
    ]
    await update.message.reply_text(
        t(lang, "choose_payment_header"), reply_markup=InlineKeyboardMarkup(keyboard)
    )

    if ADMIN_CHAT_ID:
        try:
            amount_line = f"Total: ${total:.2f}\n" if total else ""
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🔔 New booking inquiry #{booking_id}\n"
                    f"Property: {p['name']} ({p['city']}, {p['country']})\n"
                    f"Guest: {inquiry['guest_name']} ({inquiry['phone']})\n"
                    f"Telegram: @{user.username or user.id}\n"
                    f"Dates: {inquiry['check_in']} → {inquiry['check_out']}\n"
                    f"Guests: {guests}\n"
                    f"{amount_line}"
                ),
            )
        except Exception as e:
            logger.warning(f"Could not notify admin: {e}")

    context.user_data.pop("inquiry", None)
    return ConversationHandler.END


# ---------- Payment method selection ----------

async def select_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)
    _, method, booking_id_str = query.data.split("_")
    booking_id = int(booking_id_str)

    reference = f"MS-{booking_id}"
    db.set_booking_payment_method(booking_id, method, reference)

    if not payments.is_configured(method):
        await query.edit_message_text(t(lang, "payment_not_configured"))
        return

    booking = db.get_booking(booking_id)
    details = payments.build_details_block(method, reference)

    amount_line = ""
    if booking and booking["total_amount"]:
        amount_line = f"{t(lang, 'payment_amount_label')}: ${booking['total_amount']:.2f}\n\n"

    text = f"{t(lang, 'payment_instructions_header')}\n\n{amount_line}{details}"

    keyboard = [[InlineKeyboardButton(t(lang, "ive_paid_button"), callback_data=f"paid_{booking_id}")]]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def mark_paid_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = lang_for(update)
    booking_id = int(query.data.split("_")[1])

    db.set_booking_payment_status(booking_id, "pending_confirmation")
    await query.edit_message_text(t(lang, "payment_pending_confirmation"))

    if ADMIN_CHAT_ID:
        booking = db.get_booking(booking_id)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"💰 Payment claimed for booking #{booking_id}\n"
                    f"Property: {booking['property_name']}\n"
                    f"Method: {booking['payment_method']}\n"
                    f"Reference: {booking['payment_reference']}\n\n"
                    f"Verify payment arrived, then run /confirmpayment {booking_id}"
                ),
            )
        except Exception as e:
            logger.warning(f"Could not notify admin: {e}")


async def confirmpayment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: /confirmpayment <booking_id> — marks a booking as paid
    and checks whether this crosses a referral reward milestone."""
    if not ADMIN_CHAT_ID or str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return  # silently ignore for non-admins

    if not context.args:
        await update.message.reply_text("Usage: /confirmpayment <booking_id>")
        return

    try:
        booking_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Booking ID must be a number.")
        return

    booking = db.get_booking(booking_id)
    if not booking:
        await update.message.reply_text(f"No booking found with ID {booking_id}.")
        return

    referrer_id = db.get_referrer(booking["telegram_user_id"])
    before = db.count_successful_referrals(referrer_id) if referrer_id else 0

    db.set_booking_payment_status(booking_id, "confirmed")

    after = db.count_successful_referrals(referrer_id) if referrer_id else 0
    await update.message.reply_text(f"✅ Booking #{booking_id} marked as confirmed.")

    if referrer_id and after > before and after % REFERRAL_MILESTONE == 0:
        try:
            referrer_lang = db.get_user_language(referrer_id)
            await context.bot.send_message(
                chat_id=referrer_id,
                text=(
                    f"🎉 {t(referrer_lang, 'referral_progress', count=after, milestone=REFERRAL_MILESTONE)}\n"
                    f"{t(referrer_lang, 'referral_earned', amount=f'{REFERRAL_REWARD_AMOUNT:.0f}')}"
                ),
            )
        except Exception as e:
            logger.warning(f"Could not notify referrer: {e}")


async def cancel_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    context.user_data.pop("inquiry", None)
    await update.message.reply_text(t(lang, "inquiry_cancelled"))
    return ConversationHandler.END


async def mybookings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_for(update)
    bookings = db.get_bookings_for_user(update.message.from_user.id)
    if not bookings:
        await update.message.reply_text(t(lang, "mybookings_empty"))
        return
    lines = [t(lang, "mybookings_header") + "\n"]
    for b in bookings:
        lines.append(
            f"• {b['property_name']} ({b['city']}, {b['country']})\n"
            f"  {b['check_in']} → {b['check_out']}, {b['guests']} — _{b['status']}_"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN not set. Copy .env.example to .env and add your token from @BotFather."
        )

    db.init_db()
    db.seed_sample_properties()

    app = Application.builder().token(BOT_TOKEN).build()

    inquiry_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(inquire_start, pattern=r"^inquire_\d+$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CHECKIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_checkin)],
            CHECKOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_checkout)],
            GUESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_guests)],
        },
        fallbacks=[CommandHandler("cancel", cancel_inquiry)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("mybookings", mybookings_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("confirmpayment", confirmpayment_command))
    app.add_handler(inquiry_conv)
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern=r"^setlang_"))
    app.add_handler(CallbackQueryHandler(list_country_properties, pattern=r"^country_"))
    app.add_handler(CallbackQueryHandler(view_property, pattern=r"^view_\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_favorite, pattern=r"^fav_\d+$"))
    app.add_handler(CallbackQueryHandler(booking_com_placeholder, pattern=r"^booking_\d+$"))
    app.add_handler(CallbackQueryHandler(select_payment_method, pattern=r"^pay_(crypto|paypal|airtm|mpesa)_\d+$"))
    app.add_handler(CallbackQueryHandler(mark_paid_pending, pattern=r"^paid_\d+$"))
    app.add_handler(CallbackQueryHandler(main_menu_router))

    logger.info("MaveStay bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
