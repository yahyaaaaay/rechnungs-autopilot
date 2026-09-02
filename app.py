"""
app.py
-------
Step 2: a web form on top of invoice_generator.py — no HTML/CSS/JS needed,
Streamlit turns Python into a web UI directly.

Run it with:  streamlit run app.py
This opens a browser tab at http://localhost:8501

NOTE ON ARCHITECTURE: this file only handles UI (collecting input, showing
output). It doesn't know anything about tax rules or PDF layout — all of
that stays in invoice_generator.py. That separation is what let us add
this entire web interface without changing a single line of the invoice
logic itself.
"""

from datetime import date

import streamlit as st

from invoice_generator import (
    Seller,
    Party,
    LineItem,
    Invoice,
    next_invoice_number,
    generate_invoice_pdf,
)

st.set_page_config(page_title="Rechnungs-Autopilot", page_icon="🧾", layout="centered")

st.title("🧾 Rechnungs-Autopilot")
st.caption("Rechnung in 2 Minuten – mit allen gesetzlichen Pflichtangaben (§14/§19 UStG)")

# -----------------------------------------------------------------------
# Firmendaten (Aussteller) — normally you'd save this once and reuse it;
# for this prototype we keep it in the session so it survives while the
# tab is open, and pre-fill it so testing is fast.
# -----------------------------------------------------------------------
st.header("1. Deine Firmendaten")

col1, col2 = st.columns(2)
with col1:
    seller_name = st.text_input("Firmenname", value="Max Mustermann Malerbetrieb")
    seller_street = st.text_input("Straße + Hausnummer", value="Handwerkerstraße 12")
    seller_zip_city = st.text_input("PLZ + Ort", value="80331 München")
    seller_email = st.text_input("E-Mail", value="info@mustermann-maler.de")
with col2:
    seller_phone = st.text_input("Telefon", value="089 1234567")
    is_kleinunternehmer = st.checkbox("Ich bin Kleinunternehmer (§19 UStG)", value=True)
    seller_tax_id = st.text_input(
        "Steuernummer / USt-IdNr.",
        value="143/815/08154",
        help="Pflichtangabe – eine von beiden reicht.",
    )
    seller_bank_iban = st.text_input("IBAN", value="DE12 3456 7890 1234 5678 90")
    seller_bank_name = st.text_input("Bank", value="Musterbank München")

st.header("2. Kunde")
col3, col4 = st.columns(2)
with col3:
    customer_name = st.text_input("Name des Kunden", value="Familie Schmidt")
with col4:
    customer_street = st.text_input("Straße + Hausnummer ", value="Kundenweg 5")
customer_zip_city = st.text_input("PLZ + Ort ", value="80333 München")

st.header("3. Positionen")
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

st.header("4. Zahlungsziel & Notiz")
payment_terms_days = st.number_input("Zahlungsziel (Tage)", min_value=0, value=14)
notes = st.text_area("Notiz (optional)", value="Vielen Dank für Ihren Auftrag!")

st.divider()

# -----------------------------------------------------------------------
# Live-Vorschau der Summen — sofortiges Feedback, bevor man die PDF erzeugt
# -----------------------------------------------------------------------
if items:
    preview_net = sum(i.total_net for i in items)
    st.metric("Zwischensumme (netto)", f"{preview_net:.2f} EUR")

if st.button("📄 Rechnung erstellen", type="primary", disabled=not items):
    seller = Seller(
        name=seller_name, street=seller_street, zip_city=seller_zip_city,
        tax_id=seller_tax_id, is_kleinunternehmer=is_kleinunternehmer,
        bank_iban=seller_bank_iban, bank_name=seller_bank_name,
        email=seller_email, phone=seller_phone,
    )
    customer = Party(name=customer_name, street=customer_street, zip_city=customer_zip_city)

    invoice = Invoice(
        seller=seller,
        customer=customer,
        items=items,
        invoice_number=next_invoice_number(),
        invoice_date=date.today(),
        service_date=date.today(),
        payment_terms_days=payment_terms_days,
        notes=notes,
    )

    output_path = f"output/{invoice.invoice_number}.pdf"
    generate_invoice_pdf(invoice, output_path)

    st.success(f"Rechnung {invoice.invoice_number} erstellt — "
               f"{invoice.total_gross:.2f} EUR brutto")

    with open(output_path, "rb") as f:
        st.download_button(
            label="⬇️ PDF herunterladen",
            data=f,
            file_name=f"{invoice.invoice_number}.pdf",
            mime="application/pdf",
        )
