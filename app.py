"""
app.py
-------
Step 2 (+ Step 3 additions): a web form on top of invoice_generator.py.

NOTE ON ARCHITECTURE: this file only handles UI (collecting input, showing
output) and now also profile persistence via database.py. It still knows
nothing about tax rules or PDF layout — that stays in invoice_generator.py.

Run it with:  streamlit run app.py
This opens a browser tab at http://localhost:8501
"""

from datetime import date

import streamlit as st

from invoice_generator import Seller, Party, LineItem, Invoice, generate_invoice_pdf
from database import (
    init_db,
    normalize_seller_id,
    get_seller,
    save_seller,
    next_invoice_number,
    log_invoice,
    get_invoice_history,
)

init_db()

st.set_page_config(page_title="Rechnungs-Autopilot", page_icon="🧾", layout="centered")

# -----------------------------------------------------------------------
# Branding header. Colors themselves come from .streamlit/config.toml
# ([theme] section) — that's the robust way to reskin a Streamlit app,
# because it doesn't depend on Streamlit's internal HTML/CSS class names
# (which change between versions and would silently break a hand-rolled
# CSS hack).
# -----------------------------------------------------------------------
st.markdown(
    """
    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.2rem;">
        <span style="font-size:2.2rem;">🧾</span>
        <span style="font-size:1.9rem; font-weight:700;">Rechnungs-Autopilot</span>
    </div>
    <div style="color:#64748B; font-size:1rem; margin-bottom:1.4rem;">
        Rechnung in 2 Minuten – mit allen gesetzlichen Pflichtangaben (§14/§19 UStG)
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------
# 0. Firmen-Kennung — looks up / creates a saved profile. NOT a real login
# (see database.py docstring) — just a convenience so you don't retype
# your company data every time, and so your invoice numbers don't collide
# with another visitor's.
# -----------------------------------------------------------------------
with st.container(border=True):
    st.subheader("0. Deine Kennung")
    seller_id_raw = st.text_input(
        "Deine E-Mail-Adresse",
        value=st.session_state.get("seller_id_raw", ""),
        placeholder="du@deinefirma.de",
        help="Wird nur benutzt, um dein Firmenprofil wiederzuerkennen — kein Login/Passwort.",
        key="seller_id_raw",
    )
    seller_id = normalize_seller_id(seller_id_raw) if seller_id_raw else None

    if seller_id and st.session_state.get("loaded_seller_id") != seller_id:
        profile = get_seller(seller_id)
        if profile:
            st.session_state["seller_name"] = profile["name"] or ""
            st.session_state["seller_street"] = profile["street"] or ""
            st.session_state["seller_zip_city"] = profile["zip_city"] or ""
            st.session_state["seller_tax_id"] = profile["tax_id"] or ""
            st.session_state["is_kleinunternehmer"] = bool(profile["is_kleinunternehmer"])
            st.session_state["seller_bank_iban"] = profile["bank_iban"] or ""
            st.session_state["seller_bank_name"] = profile["bank_name"] or ""
            st.session_state["seller_phone"] = profile["phone"] or ""
            st.success(f"Profil für {seller_id} geladen — Felder unten sind ausgefüllt.")
        else:
            st.info("Neue Kennung, noch kein gespeichertes Profil. Einfach unten ausfüllen — "
                     "wird beim Erstellen der ersten Rechnung automatisch gespeichert.")
        st.session_state["loaded_seller_id"] = seller_id

# -----------------------------------------------------------------------
# 1. Firmendaten (Aussteller)
# -----------------------------------------------------------------------
with st.container(border=True):
    st.subheader("1. Deine Firmendaten")
    col1, col2 = st.columns(2)
    with col1:
        seller_name = st.text_input("Firmenname", key="seller_name",
                                     value=st.session_state.get("seller_name", "Max Mustermann Malerbetrieb"))
        seller_street = st.text_input("Straße + Hausnummer", key="seller_street",
                                       value=st.session_state.get("seller_street", "Handwerkerstraße 12"))
        seller_zip_city = st.text_input("PLZ + Ort", key="seller_zip_city",
                                         value=st.session_state.get("seller_zip_city", "80331 München"))
    with col2:
        seller_phone = st.text_input("Telefon", key="seller_phone",
                                      value=st.session_state.get("seller_phone", "089 1234567"))
        is_kleinunternehmer = st.checkbox("Ich bin Kleinunternehmer (§19 UStG)", key="is_kleinunternehmer",
                                           value=st.session_state.get("is_kleinunternehmer", True))
        seller_tax_id = st.text_input(
            "Steuernummer / USt-IdNr.", key="seller_tax_id",
            value=st.session_state.get("seller_tax_id", "143/815/08154"),
            help="Pflichtangabe – eine von beiden reicht.",
        )
        seller_bank_iban = st.text_input("IBAN", key="seller_bank_iban",
                                          value=st.session_state.get("seller_bank_iban", "DE12 3456 7890 1234 5678 90"))
        seller_bank_name = st.text_input("Bank", key="seller_bank_name",
                                          value=st.session_state.get("seller_bank_name", "Musterbank München"))

with st.container(border=True):
    st.subheader("2. Kunde")
    col3, col4 = st.columns(2)
    with col3:
        customer_name = st.text_input("Name des Kunden", value="Familie Schmidt")
    with col4:
        customer_street = st.text_input("Straße + Hausnummer ", value="Kundenweg 5")
    customer_zip_city = st.text_input("PLZ + Ort ", value="80333 München")

with st.container(border=True):
    st.subheader("3. Positionen")
    st.caption("Füg beliebig viele Zeilen hinzu (Menge x Einzelpreis netto).")

    if "num_items" not in st.session_state:
        st.session_state.num_items = 3

    items = []
    for i in range(st.session_state.num_items):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            desc = st.text_input(f"Beschreibung {i+1}", key=f"desc_{i}",
                                  value="Malerarbeiten Wohnzimmer" if i == 0 else "")
        with c2:
            qty = st.number_input(f"Menge {i+1}", key=f"qty_{i}", min_value=0.0,
                                   value=6.0 if i == 0 else 0.0, step=0.5)
        with c3:
            unit = st.text_input(f"Einheit {i+1}", key=f"unit_{i}",
                                  value="Std." if i == 0 else "Stk.")
        with c4:
            price = st.number_input(f"Preis/Einheit (netto) {i+1}", key=f"price_{i}",
                                     min_value=0.0, value=45.0 if i == 0 else 0.0, step=1.0)
        if desc and qty > 0:
            items.append(LineItem(description=desc, quantity=qty, unit=unit, unit_price_net=price))

    if st.button("+ Position hinzufügen"):
        st.session_state.num_items += 1
        st.rerun()

with st.container(border=True):
    st.subheader("4. Zahlungsziel & Notiz")
    payment_terms_days = st.number_input("Zahlungsziel (Tage)", min_value=0, value=14)
    notes = st.text_area("Notiz (optional)", value="Vielen Dank für Ihren Auftrag!")

st.divider()

# -----------------------------------------------------------------------
# Live-Vorschau der Summen
# -----------------------------------------------------------------------
if items:
    preview_net = sum(i.total_net for i in items)
    st.metric("Zwischensumme (netto)", f"{preview_net:.2f} EUR")

can_submit = bool(items) and bool(seller_id)
if not seller_id:
    st.caption("⚠️ Trag oben deine E-Mail-Adresse ein, bevor du eine Rechnung erstellst.")

if st.button("📄 Rechnung erstellen", type="primary", disabled=not can_submit):
    seller = Seller(
        name=seller_name, street=seller_street, zip_city=seller_zip_city,
        tax_id=seller_tax_id, is_kleinunternehmer=is_kleinunternehmer,
        bank_iban=seller_bank_iban, bank_name=seller_bank_name,
        email=seller_id_raw, phone=seller_phone,
    )
    customer = Party(name=customer_name, street=customer_street, zip_city=customer_zip_city)

    invoice = Invoice(
        seller=seller,
        customer=customer,
        items=items,
        invoice_number=next_invoice_number(seller_id),
        invoice_date=date.today(),
        service_date=date.today(),
        payment_terms_days=payment_terms_days,
        notes=notes,
    )

    output_path = f"output/{invoice.invoice_number}.pdf"
    generate_invoice_pdf(invoice, output_path)

    # Persist the profile (creates it on first use, updates it on later
    # visits) and log the invoice to this seller's history.
    save_seller(seller_id, {
        "name": seller_name, "street": seller_street, "zip_city": seller_zip_city,
        "tax_id": seller_tax_id, "is_kleinunternehmer": int(is_kleinunternehmer),
        "bank_iban": seller_bank_iban, "bank_name": seller_bank_name, "phone": seller_phone,
    })
    log_invoice(seller_id, invoice.invoice_number, customer_name, invoice.total_gross, invoice.invoice_date)

    st.success(f"Rechnung {invoice.invoice_number} erstellt — "
               f"{invoice.total_gross:.2f} EUR brutto — Profil gespeichert für {seller_id}")

    with open(output_path, "rb") as f:
        st.download_button(
            label="⬇️ PDF herunterladen",
            data=f,
            file_name=f"{invoice.invoice_number}.pdf",
            mime="application/pdf",
        )

# -----------------------------------------------------------------------
# Rechnungshistorie für diese Kennung
# -----------------------------------------------------------------------
if seller_id:
    history = get_invoice_history(seller_id)
    if history:
        with st.expander(f"📜 Bisherige Rechnungen für {seller_id} ({len(history)})"):
            for h in history:
                st.write(f"**{h['invoice_number']}** — {h['invoice_date']} — "
                         f"{h['customer_name']} — {h['total_gross']:.2f} EUR")
