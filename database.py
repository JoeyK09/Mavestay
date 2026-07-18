"""
MaveStay Telegram Bot — Database layer
Uses SQLite for simplicity. Swap out for Postgres later by changing
the connection logic in get_conn() if the project grows.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "mavestay.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                country TEXT NOT NULL,
                price_per_night REAL NOT NULL,
                bedrooms INTEGER NOT NULL,
                description TEXT,
                photo_url TEXT,
                rating REAL DEFAULT 4.5,
                review_count INTEGER DEFAULT 0,
                tag TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                telegram_username TEXT,
                guest_name TEXT,
                phone TEXT,
                check_in TEXT,
                check_out TEXT,
                guests INTEGER,
                status TEXT DEFAULT 'pending',
                total_amount REAL,
                payment_method TEXT,
                payment_reference TEXT,
                payment_status TEXT DEFAULT 'unpaid',
                created_at TEXT,
                FOREIGN KEY (property_id) REFERENCES properties (id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'en',
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                telegram_user_id INTEGER NOT NULL,
                property_id INTEGER NOT NULL,
                created_at TEXT,
                PRIMARY KEY (telegram_user_id, property_id),
                FOREIGN KEY (property_id) REFERENCES properties (id)
            )
        """)


def seed_sample_properties():
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM properties").fetchone()["c"]
        if existing > 0:
            return
        # (name, city, country, price, bedrooms, description, rating, review_count, tag)
        sample = [
            ("Sunset Villa", "Lagos", "Nigeria", 85.0, 3,
             "Cozy 3-bedroom villa with a private pool, 10 mins from the beach.",
             4.8, 132, "popular"),
            ("Downtown Loft", "Nairobi", "Kenya", 45.0, 1,
             "Modern studio loft in the city center, great for solo travelers or couples.",
             4.6, 58, None),
            ("Garden Retreat", "Accra", "Ghana", 60.0, 2,
             "Quiet 2-bedroom apartment with a private garden and fast wifi.",
             4.7, 41, "new"),
            ("Skyline Suite", "Kigali", "Rwanda", 70.0, 2,
             "High-rise apartment with panoramic city views and 24/7 security.",
             4.9, 89, "popular"),
            ("Riverside Cabin", "Cape Town", "South Africa", 95.0, 2,
             "Charming cabin near the waterfront with mountain views.",
             4.8, 76, None),
            ("Casa Bonita", "Barcelona", "Spain", 110.0, 2,
             "Bright apartment steps from the beach, walkable to everything.",
             4.7, 204, "popular"),
            ("Le Petit Marais", "Paris", "France", 140.0, 1,
             "Classic Parisian studio in the heart of Le Marais.",
             4.9, 312, "popular"),
            ("Lisbon Terrace House", "Lisbon", "Portugal", 90.0, 3,
             "Tiled townhouse with a rooftop terrace overlooking the river.",
             4.6, 67, "new"),
            ("Dubai Marina View", "Dubai", "UAE", 180.0, 2,
             "Luxury high-rise apartment with full marina views and pool access.",
             4.9, 245, "popular"),
            ("Bangkok Riverside Condo", "Bangkok", "Thailand", 55.0, 1,
             "Modern condo with river views, close to nightlife and markets.",
             4.5, 98, None),
            ("Bali Jungle Bungalow", "Ubud", "Indonesia", 65.0, 1,
             "Private bungalow surrounded by rice paddies, with an open-air bath.",
             4.9, 421, "popular"),
            ("Brooklyn Brownstone", "New York", "USA", 220.0, 3,
             "Classic brownstone apartment in a leafy Brooklyn neighborhood.",
             4.8, 156, None),
            ("Copacabana Flat", "Rio de Janeiro", "Brazil", 75.0, 2,
             "Beachfront apartment steps from Copacabana with ocean views.",
             4.7, 189, "new"),
            ("Tokyo Compact Studio", "Tokyo", "Japan", 80.0, 1,
             "Efficient, beautifully designed studio near Shinjuku station.",
             4.8, 143, None),
        ]
        conn.executemany(
            """INSERT INTO properties
               (name, city, country, price_per_night, bedrooms, description,
                rating, review_count, tag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            sample,
        )


# ---------- Properties ----------

def get_countries():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT country FROM properties WHERE active = 1 ORDER BY country"
        ).fetchall()
        return [r["country"] for r in rows]


def get_properties_by_country(country: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM properties WHERE active = 1 AND country = ? ORDER BY id",
            (country,),
        ).fetchall()


def get_active_properties():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM properties WHERE active = 1 ORDER BY id"
        ).fetchall()


def get_property(property_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM properties WHERE id = ?", (property_id,)
        ).fetchone()


# ---------- Users / language ----------

def get_user_language(telegram_user_id: int, fallback: str = "en") -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return row["language"] if row else fallback


def user_exists(telegram_user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return row is not None


def set_user_language(telegram_user_id: int, language: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (telegram_user_id, language, referral_code, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_user_id) DO UPDATE SET language = excluded.language""",
            (telegram_user_id, language, format(telegram_user_id, "x"),
             datetime.utcnow().isoformat()),
        )


# ---------- Referrals ----------

def get_referral_code(telegram_user_id: int) -> str:
    """Every user gets a stable referral code (hex of their Telegram ID)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referral_code FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return row["referral_code"] if row and row["referral_code"] else format(telegram_user_id, "x")


def get_user_id_by_referral_code(code: str):
    try:
        return int(code, 16)
    except ValueError:
        return None


def set_referred_by(telegram_user_id: int, referrer_id: int):
    """Only sets referred_by if not already set and it's not a self-referral."""
    if referrer_id == telegram_user_id:
        return
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referred_by FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        if row and row["referred_by"] is None:
            conn.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_user_id = ?",
                (referrer_id, telegram_user_id),
            )


def count_successful_referrals(referrer_id: int) -> int:
    """Counts distinct referred users who have at least one confirmed booking."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(DISTINCT u.telegram_user_id) AS c
               FROM users u
               WHERE u.referred_by = ?
               AND EXISTS (
                   SELECT 1 FROM bookings b
                   WHERE b.telegram_user_id = u.telegram_user_id
                   AND b.payment_status = 'confirmed'
               )""",
            (referrer_id,),
        ).fetchone()
        return row["c"] if row else 0


def get_referrer(telegram_user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referred_by FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return row["referred_by"] if row else None


# ---------- Favorites ----------

def add_favorite(telegram_user_id: int, property_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO favorites (telegram_user_id, property_id, created_at)
               VALUES (?, ?, ?)""",
            (telegram_user_id, property_id, datetime.utcnow().isoformat()),
        )


def remove_favorite(telegram_user_id: int, property_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM favorites WHERE telegram_user_id = ? AND property_id = ?",
            (telegram_user_id, property_id),
        )


def is_favorite(telegram_user_id: int, property_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM favorites WHERE telegram_user_id = ? AND property_id = ?",
            (telegram_user_id, property_id),
        ).fetchone()
        return row is not None


def get_favorites(telegram_user_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT p.* FROM favorites f
               JOIN properties p ON f.property_id = p.id
               WHERE f.telegram_user_id = ?
               ORDER BY f.created_at DESC""",
            (telegram_user_id,),
        ).fetchall()


# ---------- Bookings ----------

def create_booking(property_id, telegram_user_id, telegram_username,
                    guest_name, phone, check_in, check_out, guests, total_amount=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bookings
               (property_id, telegram_user_id, telegram_username, guest_name,
                phone, check_in, check_out, guests, status, total_amount,
                payment_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 'unpaid', ?)""",
            (property_id, telegram_user_id, telegram_username, guest_name,
             phone, check_in, check_out, guests, total_amount,
             datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_booking(booking_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, p.name AS property_name, p.price_per_night
               FROM bookings b JOIN properties p ON b.property_id = p.id
               WHERE b.id = ?""",
            (booking_id,),
        ).fetchone()


def set_booking_payment_method(booking_id: int, method: str, reference: str):
    with get_conn() as conn:
        conn.execute(
            """UPDATE bookings SET payment_method = ?, payment_reference = ?
               WHERE id = ?""",
            (method, reference, booking_id),
        )


def set_booking_payment_status(booking_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bookings SET payment_status = ? WHERE id = ?",
            (status, booking_id),
        )


def get_bookings_by_payment_status(payment_status: str):
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, p.name AS property_name, p.city, p.country
               FROM bookings b JOIN properties p ON b.property_id = p.id
               WHERE b.payment_status = ?
               ORDER BY b.created_at ASC""",
            (payment_status,),
        ).fetchall()


def get_bookings_for_user(telegram_user_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, p.name AS property_name, p.city, p.country
               FROM bookings b JOIN properties p ON b.property_id = p.id
               WHERE b.telegram_user_id = ?
               ORDER BY b.created_at DESC""",
            (telegram_user_id,),
        ).fetchall()
