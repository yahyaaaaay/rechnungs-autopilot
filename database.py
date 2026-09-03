"""
database.py
------------
Adds persistence on top of invoice_generator.py: seller profiles saved by
a "Firmen-Kennung" (we use the seller's email as a simple identifier), a
separate invoice-number sequence PER seller, and a short invoice history.

WHY THIS WAS NEEDED
Two real problems with the first version of the app:
1. Every visitor had to retype their company data every single time —
   nothing was remembered between visits.
2. `invoice_counter.json` was ONE shared counter for every visitor of the
   deployed app. If two different businesses used the live app at the same
   time, their invoice numbers would interleave — breaking the legal
   requirement that each business's own numbering be gap-free.

IMPORTANT — WHAT THIS IS *NOT*: a login system. The "Firmen-Kennung" (we
use email) is just a lookup key, not a password-protected account. Anyone
who knows/guesses someone else's email could load their profile. That's a
deliberate, honest simplification for this stage (fast to build, fine for
a small first test with a handful of trusted Handwerker) — real accounts
with authentication would be a later, separate step once there's a reason
to invest in it (e.g. paying customers).

SQLite is used because it's a single file (rechnungen.db), needs no
separate server to install/run, and Python's standard library talks to it
directly (the `sqlite3` module — no extra dependency).
"""

import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = "rechnungen.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["name"]
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the tables if they don't exist yet. Safe to call every time
    the app starts — CREATE TABLE IF NOT EXISTS is a no-op if it's already
    there."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sellers (
                seller_id TEXT PRIMARY KEY,
                name TEXT, street TEXT, zip_city TEXT,
                tax_id TEXT, is_kleinunternehmer INTEGER,
                bank_iban TEXT, bank_name TEXT, phone TEXT,
                invoice_year INTEGER DEFAULT 0,
                invoice_seq INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id TEXT,
                invoice_number TEXT,
                invoice_date TEXT,
                customer_name TEXT,
                total_gross REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def normalize_seller_id(raw: str) -> str:
    return raw.strip().lower()


def get_seller(seller_id: str) -> dict | None:
    """Return the saved profile for this seller_id, or None if there isn't one yet."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sellers WHERE seller_id = ?", (seller_id,)
        ).fetchone()
        return dict(row) if row else None


def save_seller(seller_id: str, data: dict) -> None:
    """Create or update a seller profile (an 'upsert'). We keep the
    existing invoice_year/invoice_seq untouched here — those are only
    changed by next_invoice_number below."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sellers (seller_id, name, street, zip_city, tax_id,
                                  is_kleinunternehmer, bank_iban, bank_name, phone)
            VALUES (:seller_id, :name, :street, :zip_city, :tax_id,
                    :is_kleinunternehmer, :bank_iban, :bank_name, :phone)
            ON CONFLICT(seller_id) DO UPDATE SET
                name=excluded.name, street=excluded.street, zip_city=excluded.zip_city,
                tax_id=excluded.tax_id, is_kleinunternehmer=excluded.is_kleinunternehmer,
                bank_iban=excluded.bank_iban, bank_name=excluded.bank_name,
                phone=excluded.phone
        """, {"seller_id": seller_id, **data})


def next_invoice_number(seller_id: str, prefix: str = "RE") -> str:
    """Return the next invoice number for THIS seller specifically (not a
    global counter), e.g. RE-2026-0004, and persist the updated sequence.
    Resets to 1 automatically at the start of a new calendar year."""
    year = date.today().year
    with get_connection() as conn:
        row = conn.execute(
            "SELECT invoice_year, invoice_seq FROM sellers WHERE seller_id = ?",
            (seller_id,),
        ).fetchone()

        if row is None:
            # Seller doesn't exist yet (shouldn't normally happen if
            # save_seller was called first, but handle it defensively).
            conn.execute(
                "INSERT INTO sellers (seller_id, invoice_year, invoice_seq) VALUES (?, ?, 1)",
                (seller_id, year),
            )
            seq = 1
        elif row["invoice_year"] != year:
            # First invoice of a new calendar year -> restart at 1.
            conn.execute(
                "UPDATE sellers SET invoice_year = ?, invoice_seq = 1 WHERE seller_id = ?",
                (year, seller_id),
            )
            seq = 1
        else:
            seq = row["invoice_seq"] + 1
            conn.execute(
                "UPDATE sellers SET invoice_seq = ? WHERE seller_id = ?",
                (seq, seller_id),
            )

    return f"{prefix}-{year}-{seq:04d}"


def log_invoice(seller_id: str, invoice_number: str, customer_name: str,
                 total_gross: float, invoice_date: date) -> None:
    """Record one generated invoice so the seller can see their history."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO invoices (seller_id, invoice_number, invoice_date, customer_name, total_gross)
            VALUES (?, ?, ?, ?, ?)
        """, (seller_id, invoice_number, invoice_date.isoformat(), customer_name, total_gross))


def get_invoice_history(seller_id: str, limit: int = 20) -> list[dict]:
    """Most recent invoices for this seller first."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT invoice_number, invoice_date, customer_name, total_gross
            FROM invoices WHERE seller_id = ?
            ORDER BY id DESC LIMIT ?
        """, (seller_id, limit)).fetchall()
        return [dict(r) for r in rows]
