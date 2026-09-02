"""
invoice_generator.py
---------------------
The core of the invoicing tool: turns structured data (seller, customer,
line items) into a legally correct German invoice PDF.

WHY THIS IS THE HEART OF THE PRODUCT
Every invoice over 250 EUR (gross) issued in Germany must contain a fixed
set of mandatory fields under § 14 UStG (Umsatzsteuergesetz). Small
businesses under the "Kleinunternehmerregelung" (§ 19 UStG) additionally
need a specific legal wording instead of charging VAT. This module builds
those rules into the PDF generation itself, so a tradesperson can't
accidentally forget a required field.

Dependencies: fpdf2 (pip install fpdf2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fpdf import FPDF


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Party:
    """A business or person: either the seller (Aussteller) or the customer
    (Empfänger). § 14 UStG requires BOTH full names and addresses on the
    invoice."""
    name: str
    street: str
    zip_city: str  # e.g. "80331 München"


@dataclass
class Seller(Party):
    """The seller additionally needs a tax identifier and, if they are a
    Kleinunternehmer (§ 19 UStG), that status affects how tax is shown."""
    tax_id: str = ""             # Steuernummer or USt-IdNr. (one is required)
    is_kleinunternehmer: bool = False
    bank_iban: str = ""
    bank_name: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class LineItem:
    """One row of the invoice: § 14 UStG requires quantity and a description
    of the goods/service for each item."""
    description: str
    quantity: float
    unit: str          # e.g. "Std." (hours), "Stk." (pieces), "pauschal"
    unit_price_net: float   # net price per unit, in EUR
    tax_rate: float = 19.0  # % VAT — ignored entirely for Kleinunternehmer

    @property
    def total_net(self) -> float:
        return round(self.quantity * self.unit_price_net, 2)


@dataclass
class Invoice:
    """Everything needed for one invoice."""
    seller: Seller
    customer: Party
    items: list[LineItem]
    invoice_number: str
    invoice_date: date
    service_date: date          # Leistungsdatum — required, can differ from invoice_date
    payment_terms_days: int = 14
    notes: str = ""

    @property
    def total_net(self) -> float:
        return round(sum(item.total_net for item in self.items), 2)

    def tax_by_rate(self) -> dict[float, float]:
        """Group tax amounts by rate — required when items have different
        VAT rates (e.g. 19% and 7%)."""
        totals: dict[float, float] = {}
        for item in self.items:
            rate = 0.0 if self.seller.is_kleinunternehmer else item.tax_rate
            totals[rate] = totals.get(rate, 0.0) + item.total_net * (rate / 100)
        return {rate: round(amount, 2) for rate, amount in totals.items()}

    @property
    def total_tax(self) -> float:
        return round(sum(self.tax_by_rate().values()), 2)

    @property
    def total_gross(self) -> float:
        return round(self.total_net + self.total_tax, 2)


# ---------------------------------------------------------------------------
# Sequential invoice numbering
# ---------------------------------------------------------------------------
# § 14 UStG requires a unique, consecutive invoice number ("fortlaufende
# Nummer mit einer oder mehreren Zahlenreihen"). We persist a counter to
# disk so numbers never repeat or get reused across runs of the script.

COUNTER_FILE = Path("invoice_counter.json")


def next_invoice_number(prefix: str = "RE") -> str:
    """Return the next invoice number, e.g. RE-2026-0007, and persist the
    updated counter so the next call continues from here."""
    year = date.today().year
    if COUNTER_FILE.exists():
        state = json.loads(COUNTER_FILE.read_text())
    else:
        state = {}

    key = str(year)
    last = state.get(key, 0)
    new_number = last + 1
    state[key] = new_number
    COUNTER_FILE.write_text(json.dumps(state, indent=2))

    return f"{prefix}-{year}-{new_number:04d}"


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

class InvoicePDF(FPDF):
    def header(self):
        pass  # we lay out the header manually per-invoice instead

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 4, f"Seite {self.page_no()}", align="C")


def generate_invoice_pdf(invoice: Invoice, output_path: str) -> str:
    """Render `invoice` to a PDF file at `output_path`. Returns the path."""
    pdf = InvoicePDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    s = invoice.seller

    # --- Absenderzeile (small line above the address field — common German
    # business-letter convention, also doubles as a return address) ---
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4, f"{s.name} | {s.street} | {s.zip_city}")
    pdf.ln(10)

    # --- Empfänger (customer address block) — mandatory: full name + address ---
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(90, 5, f"{invoice.customer.name}\n{invoice.customer.street}\n{invoice.customer.zip_city}")

    # --- Absender-Infobox rechts (contact + tax id) ---
    pdf.set_xy(120, 20)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(70, 5, s.name, align="R")
    pdf.set_xy(120, pdf.get_y())
    pdf.set_font("Helvetica", "", 9)
    contact_lines = [s.street, s.zip_city]
    if s.email:
        contact_lines.append(s.email)
    if s.phone:
        contact_lines.append(s.phone)
    if s.tax_id:
        contact_lines.append(f"Steuernr./USt-IdNr.: {s.tax_id}")
    pdf.multi_cell(70, 5, "\n".join(contact_lines), align="R")

    pdf.ln(14)

    # --- Titel + Kernangaben (invoice number, dates — all mandatory) ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "Rechnung", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    meta = [
        ("Rechnungsnummer", invoice.invoice_number),
        ("Rechnungsdatum", invoice.invoice_date.strftime("%d.%m.%Y")),
        ("Leistungsdatum", invoice.service_date.strftime("%d.%m.%Y")),
        ("Zahlungsziel", f"{invoice.payment_terms_days} Tage netto"),
    ]
    for label, value in meta:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 6, f"{label}:")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, value, ln=True)

    pdf.ln(6)

    # --- Positionstabelle (mandatory: quantity + description per item) ---
    col_widths = [80, 20, 20, 25, 25]
    headers = ["Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt (netto)"]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for item in invoice.items:
        pdf.cell(col_widths[0], 7, item.description, border=1)
        pdf.cell(col_widths[1], 7, f"{item.quantity:g}", border=1, align="R")
        pdf.cell(col_widths[2], 7, item.unit, border=1, align="C")
        pdf.cell(col_widths[3], 7, f"{item.unit_price_net:.2f} EUR", border=1, align="R")
        pdf.cell(col_widths[4], 7, f"{item.total_net:.2f} EUR", border=1, align="R")
        pdf.ln()

    pdf.ln(4)

    # --- Summenblock ---
    label_w = sum(col_widths[:4])
    val_w = col_widths[4]

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(label_w, 6, "Gesamtbetrag (netto):", align="R")
    pdf.cell(val_w, 6, f"{invoice.total_net:.2f} EUR", align="R", ln=True)

    if s.is_kleinunternehmer:
        # § 19 UStG: mandatory wording instead of showing VAT.
        pdf.cell(label_w, 6, "", align="R")
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(
            val_w + label_w, 5,
            "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
            align="R",
        )
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_w, 7, "Rechnungsbetrag:", align="R")
        pdf.cell(val_w, 7, f"{invoice.total_gross:.2f} EUR", align="R", ln=True)
    else:
        for rate, amount in invoice.tax_by_rate().items():
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(label_w, 6, f"zzgl. {rate:.0f}% USt:", align="R")
            pdf.cell(val_w, 6, f"{amount:.2f} EUR", align="R", ln=True)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_w, 7, "Rechnungsbetrag (brutto):", align="R")
        pdf.cell(val_w, 7, f"{invoice.total_gross:.2f} EUR", align="R", ln=True)

    pdf.ln(10)

    if invoice.notes:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, invoice.notes)
        pdf.ln(4)

    # --- Zahlungsinformationen ---
    if s.bank_iban:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, f"Bitte überweisen Sie den Betrag bis zum Zahlungsziel an:\n"
                              f"{s.bank_name}  |  IBAN: {s.bank_iban}")

    pdf.output(output_path)
    return output_path
