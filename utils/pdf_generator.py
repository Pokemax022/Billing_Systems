import os
import traceback
from flask import render_template, current_app, has_app_context
from num2words import num2words
import qrcode
import base64
from io import BytesIO
from playwright.sync_api import sync_playwright

def _get_pdf_dir():
    """Return configured PDF storage directory with auto-creation."""
    if has_app_context():
        pdf_dir = current_app.config.get('PDF_FOLDER', os.path.join(os.getcwd(), 'pdf'))
    else:
        pdf_dir = os.path.join(os.getcwd(), 'pdf')
    os.makedirs(pdf_dir, exist_ok=True)
    return pdf_dir

TEMPLATES = {
    'classic':  'pdf/quotation_template.html',
    'premium':  'pdf/quotation_premium.html',
    'minimal':  'pdf/quotation_minimal.html',
    'dhruv':    'pdf/quotation_dhruv.html',
    'adarsh':   'pdf/quotation_adarsh.html',
    'adarsh_v2':'pdf/quotation_adarsh_v2.html',
}

def _build_context(quote, company):
    """Build shared context dict for all templates."""
    # QR code as base64
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    comp_name = company.name if company else 'MISTHI ENTERPRISE'
    qr.add_data(f"upi://pay?pa=rvandana616@okaxis&pn={comp_name.replace(' ', '%20')}&am={quote.grand_total}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    qr_data_uri = f"data:image/png;base64,{qr_b64}"

    # Amount in words
    try:
        amount_in_words = num2words(int(quote.grand_total), lang='en_IN').title() + " Rupees Only"
    except Exception:
        amount_in_words = f"{quote.grand_total:,.0f} Rupees Only"

    return dict(quote=quote, company=company,
                amount_in_words=amount_in_words,
                qr_data_uri=qr_data_uri)


def render_quotation_html(quote, company, template='classic'):
    """Render quotation as HTML string (used for browser preview)."""
    tpl = TEMPLATES.get(template, TEMPLATES['classic'])
    ctx = _build_context(quote, company)
    return render_template(tpl, **ctx)


def generate_quotation_pdf(quote, company, template='classic'):
    """Generate PDF and return output file path."""
    pdf_dir = _get_pdf_dir()

    html_out = render_quotation_html(quote, company, template)

    cust_name = quote.customer.name if quote.customer else 'Customer'
    safe_name = "".join(c for c in cust_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    filename = f"QUOTATION_{safe_name}_{quote.date}_{template}.pdf"
    output_path = os.path.join(pdf_dir, filename)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()
            page.set_content(html_out, wait_until='domcontentloaded')
            page.wait_for_timeout(600)
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"}
            )
            browser.close()
    except Exception as e:
        print(f"[PDF ERROR] {e}")
        traceback.print_exc()
        raise

    return output_path


# ─────────────────────────────────────────────────────
# Invoice PDF functions
# ─────────────────────────────────────────────────────

def _build_invoice_context(inv, company):
    """Build shared context dict for invoice templates."""
    # QR code for payment
    upi_id = 'rvandana616@okaxis'
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    comp_name = company.name if company else 'MISTHI ENTERPRISE'
    qr.add_data(f"upi://pay?pa={upi_id}&pn={comp_name.replace(' ', '%20')}&am={inv.balance_due}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    qr_data_uri = f"data:image/png;base64,{qr_b64}"

    # Amount in words
    try:
        amount_in_words = num2words(int(inv.grand_total), lang='en_IN').title() + " Rupees Only"
    except Exception:
        amount_in_words = f"{inv.grand_total:,.0f} Rupees Only"

    return dict(inv=inv, company=company,
                amount_in_words=amount_in_words,
                qr_data_uri=qr_data_uri)


def render_invoice_html(inv, company):
    """Render invoice as HTML string (used for browser preview and PDF)."""
    ctx = _build_invoice_context(inv, company)
    return render_template('pdf/invoice_premium.html', **ctx)


def generate_invoice_pdf(inv, company):
    """Generate invoice PDF and return output file path."""
    pdf_dir = _get_pdf_dir()

    html_out = render_invoice_html(inv, company)

    cust_name = (inv.customer.name if inv.customer else 'Customer')
    safe_name = "".join(c for c in cust_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    safe_inv = inv.invoice_number.replace('-', '_')
    filename = f"INVOICE_{safe_inv}_{safe_name}_{inv.date}.pdf"
    output_path = os.path.join(pdf_dir, filename)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()
            page.set_content(html_out, wait_until='domcontentloaded')
            page.wait_for_timeout(600)
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"}
            )
            browser.close()
    except Exception as e:
        print(f"[INVOICE PDF ERROR] {e}")
        traceback.print_exc()
        raise

    return output_path

