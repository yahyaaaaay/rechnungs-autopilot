"""
example_invoice.py
-------------------
Shows how to use invoice_generator.py to create a real invoice.

This is deliberately written as plain, readable Python — no web framework,
no database yet. Change the values below to your own data and run:

    python3 example_invoice.py

Two example invoices are generated in output/: one as a regular
VAT-charging business, one as a Kleinunternehmer (§ 19 UStG) — so you can
see how the PDF differs between the two.
"""

from datetime import date

from invoice_generator import (
    Seller,
    Party,
    LineItem,
    Invoice,
    next_invoice_number,
    generate_invoice_pdf,
)


def build_example_seller(kleinunternehmer: bool) -> Seller:
    return Seller(
        name="Max Mustermann Malerbetrieb",
        street="Handwerkerstraße 12",
        zip_city="80331 München",
        tax_id="DE123456789" if not kleinunternehmer else "143/815/08154",
        is_kleinunternehmer=kleinunternehmer,
        bank_iban="DE12 3456 7890 1234 5678 90",
        bank_name="Musterbank München",
        email="info@mustermann-maler.de",
        phone="089 1234567",
    )


def build_example_customer() -> Party:
    return Party(
        name="Familie Schmidt",
        street="Kundenweg 5",
        zip_city="80333 München",
    )


def build_example_items() -> list[LineItem]:
    return [
        LineItem(description="Malerarbeiten Wohnzimmer (Wände streichen)",
                  quantity=6, unit="Std.", unit_price_net=45.00),
        LineItem(description="Malervlies inkl. Verarbeitung",
                  quantity=2, unit="Rolle", unit_price_net=35.00),
        LineItem(description="Anfahrt", quantity=1, unit="pauschal", unit_price_net=20.00),
    ]


def main():
    today = date.today()

    # --- Example 1: regular business (charges 19% VAT) ---
    seller = build_example_seller(kleinunternehmer=False)
    invoice = Invoice(
        seller=seller,
        customer=build_example_customer(),
        items=build_example_items(),
        invoice_number=next_invoice_number(),
        invoice_date=today,
        service_date=today,
        payment_terms_days=14,
        notes="Vielen Dank für Ihren Auftrag!",
    )
    path = generate_invoice_pdf(invoice, "output/rechnung_regelbesteuerung.pdf")
    print(f"Erstellt: {path}  (Rechnungsnummer {invoice.invoice_number}, "
          f"Gesamt {invoice.total_gross:.2f} EUR)")

    # --- Example 2: Kleinunternehmer (no VAT shown, mandatory § 19 wording) ---
    seller_ku = build_example_seller(kleinunternehmer=True)
    invoice_ku = Invoice(
        seller=seller_ku,
        customer=build_example_customer(),
        items=build_example_items(),
        invoice_number=next_invoice_number(),
        invoice_date=today,
        service_date=today,
        payment_terms_days=14,
        notes="Vielen Dank für Ihren Auftrag!",
    )
    path_ku = generate_invoice_pdf(invoice_ku, "output/rechnung_kleinunternehmer.pdf")
    print(f"Erstellt: {path_ku}  (Rechnungsnummer {invoice_ku.invoice_number}, "
          f"Gesamt {invoice_ku.total_gross:.2f} EUR)")


if __name__ == "__main__":
    main()
