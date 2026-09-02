# Rechnungs-Autopilot

Generates legally correct German invoices (Rechnungen) as PDFs from
structured data — a real (if early) invoicing tool for tradespeople and
solo self-employed people, with a proper web form on top.

- **Step 1** (`invoice_generator.py`): pure Python core — data model + PDF rendering.
- **Step 2** (`app.py`): a Streamlit web form on top of the exact same core — no HTML/CSS/JS needed.

## What it does

- Builds a PDF invoice containing every field required under German law
  (§ 14 UStG): full seller & buyer name/address, tax ID, invoice date,
  service date, a unique sequential invoice number, itemized quantities
  and descriptions, net total, VAT rate/amount, gross total.
- Supports **Kleinunternehmer** (§ 19 UStG) sellers: automatically shows
  the required "no VAT charged" wording instead of a tax line.
- Auto-increments the invoice number (persisted in `invoice_counter.json`,
  reset per calendar year) so numbers are always unique and consecutive —
  a legal requirement, not just a nice-to-have.

## Project structure

```
rechnungs-app/
├── invoice_generator.py   # core: data model (Seller, Party, LineItem, Invoice) + PDF rendering
├── app.py                 # Streamlit web form — the "app" you actually run day-to-day
├── example_invoice.py     # example usage of the core without any UI — good for learning/testing
├── invoice_counter.json   # auto-created; tracks the next invoice number
├── output/                # generated PDFs land here
├── requirements.txt
└── README.md
```

## Setup & run

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Option A — the web app (recommended, this is the actual product):**

```bash
streamlit run app.py
```

This opens `http://localhost:8501` in your browser automatically. Fill in
the form, click "Rechnung erstellen", download the PDF. Every field is
pre-filled with example data so you can try it immediately, then just
overwrite the values with your own.

**Option B — the plain-Python core, no UI (for learning/testing):**

```bash
python3 example_invoice.py
```

This creates two example PDFs directly in `output/`: one for a regular
VAT-charging business and one for a Kleinunternehmer, so you can compare
the two side by side.

## How to use it with your own data

Open `example_invoice.py` and change the values in `build_example_seller`,
`build_example_customer`, and `build_example_items` to your own — or
better, once you're comfortable with the code, write a new script that
imports `invoice_generator.py` and builds an `Invoice` from your own data
source (a form, a JSON file, eventually a database).

## Why it's structured this way (for your own learning)

- `invoice_generator.py` is split into **data model** (dataclasses:
  `Seller`, `Party`, `LineItem`, `Invoice`) and **rendering**
  (`generate_invoice_pdf`). This separation matters: the data model has no
  idea a PDF exists, and the rendering code doesn't do any business logic.
  That's what lets you swap the PDF renderer for, say, a web page or a
  ZUGFeRD e-invoice later without touching the data model.
- Tax calculation lives on the `Invoice` dataclass itself (`total_net`,
  `tax_by_rate`, `total_gross`) rather than being computed inline while
  drawing the PDF — so it can be unit-tested independently of anything
  PDF-related.
- The invoice-numbering logic is deliberately its own function
  (`next_invoice_number`) with its own persisted state file, because it's
  a legal requirement (uniqueness, no gaps) that has nothing to do with
  PDF layout.

## Why app.py stays thin

`app.py` only collects input and displays output — it builds a `Seller`,
`Party`, `LineItem`s and an `Invoice`, then calls `generate_invoice_pdf`.
It contains zero tax logic and zero PDF layout code. That's on purpose:
whatever UI comes next (a proper Flask/React app, a mobile-friendly PWA)
can reuse `invoice_generator.py` completely unchanged.

## Next steps

- Deploy `app.py` for free on Streamlit Community Cloud so you can test it
  with real Handwerker on their own phones/laptops (currently local-only).
- Add a small database (SQLite) so seller data doesn't need retyping and
  invoices/customers persist between sessions.
- ZUGFeRD e-invoice export (structured XML embedded in the PDF) — see the
  research notes on the 2027/2028 E-Rechnungspflicht deadlines.

## License

MIT
