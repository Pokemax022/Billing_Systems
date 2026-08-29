import os
import re
from datetime import datetime, date
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, send_file, Response, jsonify)
from flask_login import login_required
from models.invoice import Invoice, InvoiceItem, InvoicePayment
from models.customer import Customer
from models.product import Product
from models.company import CompanySettings
from database.db import db

invoices_bp = Blueprint('invoices', __name__, url_prefix='/invoices')


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _safe_float(val, default=0.0):
    """Safely parse float numbers from string inputs, stripping currency symbols and commas."""
    if val is None or val == '':
        return default
    try:
        clean = re.sub(r'[^\d\.-]', '', str(val))
        return float(clean) if clean else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    """Safely parse integer numbers from string inputs."""
    if val is None or val == '':
        return default
    try:
        clean = re.sub(r'[^\d-]', '', str(val))
        return int(float(clean)) if clean else default
    except (ValueError, TypeError):
        return default


def _parse_form_date(val, default=None):
    """Safely parse date strings from form inputs."""
    if not val:
        return default
    try:
        return datetime.strptime(str(val).strip()[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def generate_invoice_number():
    """Generate next unique invoice number like INV-1001, INV-1002 safely."""
    all_nums = []
    for inv in Invoice.query.all():
        if inv.invoice_number and '-' in inv.invoice_number:
            try:
                all_nums.append(int(inv.invoice_number.split('-')[-1]))
            except (IndexError, ValueError):
                pass
    start = max(all_nums, default=1000) + 1
    candidate = f"INV-{start:04d}"
    while Invoice.query.filter_by(invoice_number=candidate).first():
        start += 1
        candidate = f"INV-{start:04d}"
    return candidate


def _is_interstate(company, customer):
    """Determine if transaction is interstate for GST (IGST vs CGST+SGST)."""
    if company and customer and company.gstin and customer.gst_number:
        return company.gstin[:2] != customer.gst_number[:2]
    if customer and customer.gst_number and not customer.gst_number.startswith('24'):
        return True
    return False


def _build_invoice_from_form(inv, form, is_edit=False):
    """Parse form data and populate an Invoice instance. Returns the invoice."""
    cid = form.get('customer_id', '').strip()
    inv.customer_id = int(cid) if cid and cid.isdigit() else None
    inv.date = _parse_form_date(form.get('date'), default=date.today())
    inv.due_date = _parse_form_date(form.get('due_date'), default=None)
    inv.reference_number = form.get('reference_number', '').strip()
    inv.payment_method = form.get('payment_method', '').strip()
    inv.notes = form.get('notes', '').strip()
    inv.terms_conditions = form.get('terms_conditions', '').strip()

    # Charges
    inst_rate = _safe_float(form.get('installation_charges'), 0.0)
    inst_qty = _safe_int(form.get('installation_qty'), 1)
    inv.installation_rate = inst_rate
    inv.installation_qty = inst_qty
    inv.installation_charges = inst_rate * inst_qty
    inv.wiring_charges = _safe_float(form.get('wiring_charges'), 0.0)
    inv.transport_charges = _safe_float(form.get('transport_charges'), 0.0)

    # Discount
    inv.discount_type = form.get('discount_type', 'percent')
    inv.discount_value = _safe_float(form.get('discount_value'), 0.0)

    # Items
    if is_edit:
        InvoiceItem.query.filter_by(invoice_id=inv.id).delete()

    names = form.getlist('item_name[]')
    descs = form.getlist('item_desc[]')
    hsns = form.getlist('item_hsn[]')
    qtys = form.getlist('item_qty[]')
    rates = form.getlist('item_rate[]')
    disc_pcts = form.getlist('item_discount[]')
    gst_pcts = form.getlist('item_gst[]')
    prod_ids = form.getlist('item_product_id[]')

    company = CompanySettings.query.first()
    customer = db.session.get(Customer, inv.customer_id) if inv.customer_id else None
    interstate = _is_interstate(company, customer)

    sub_total = 0.0
    cgst_total = 0.0
    sgst_total = 0.0
    igst_total = 0.0

    for i, name in enumerate(names):
        name = name.strip()
        if not name:
            continue

        qty = _safe_float(qtys[i] if i < len(qtys) else 1.0, 1.0) or 1.0
        rate = _safe_float(rates[i] if i < len(rates) else 0.0, 0.0)
        disc_pct = _safe_float(disc_pcts[i] if i < len(disc_pcts) else 0.0, 0.0)
        gst_pct = _safe_float(gst_pcts[i] if i < len(gst_pcts) else 18.0, 18.0)

        line_gross = qty * rate
        line_disc = line_gross * (disc_pct / 100)
        taxable = line_gross - line_disc
        tax_amt = taxable * (gst_pct / 100)

        sub_total += taxable
        if interstate:
            igst_total += tax_amt
        else:
            cgst_total += tax_amt / 2
            sgst_total += tax_amt / 2

        p_id_raw = prod_ids[i] if i < len(prod_ids) else None
        p_id = int(p_id_raw) if (p_id_raw and str(p_id_raw).isdigit()) else None

        item = InvoiceItem(
            invoice_id=inv.id,
            product_id=p_id,
            name=name,
            description=descs[i].strip() if i < len(descs) else '',
            hsn_code=hsns[i].strip() if i < len(hsns) else '',
            quantity=qty,
            unit_price=rate,
            discount_percent=disc_pct,
            gst_percent=gst_pct,
            taxable_value=round(taxable, 2),
            tax_amount=round(tax_amt, 2),
            line_total=round(taxable + tax_amt, 2),
        )
        db.session.add(item)

    inv.sub_total = round(sub_total, 2)
    inv.cgst_total = round(cgst_total, 2)
    inv.sgst_total = round(sgst_total, 2)
    inv.igst_total = round(igst_total, 2)

    # Apply invoice-level discount
    total_tax = cgst_total + sgst_total + igst_total
    pre_discount_total = sub_total + total_tax + inv.installation_charges + inv.wiring_charges + inv.transport_charges

    if inv.discount_type == 'percent':
        inv.discount_amount = round(sub_total * (inv.discount_value / 100), 2)
    else:
        inv.discount_amount = round(inv.discount_value, 2)

    inv.grand_total = round(pre_discount_total - inv.discount_amount, 2)

    # Recalculate balance
    inv.paid_amount = round(sum(p.amount for p in inv.payments), 2)
    inv.balance_due = round(max(0.0, inv.grand_total - inv.paid_amount), 2)

    # Auto payment_status
    manual_status = form.get('payment_status', '').strip()
    if manual_status in ('Paid', 'Partially Paid', 'Pending', 'Overdue', 'Cancelled'):
        inv.payment_status = manual_status
    else:
        if inv.paid_amount <= 0:
            inv.payment_status = 'Overdue' if (inv.due_date and date.today() > inv.due_date) else 'Pending'
        elif inv.balance_due <= 0:
            inv.payment_status = 'Paid'
        else:
            inv.payment_status = 'Partially Paid'

    return inv


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────

@invoices_bp.route('/')
@login_required
def index():
    # Stats
    all_inv = Invoice.query.all()
    total_count = len(all_inv)
    paid_count = sum(1 for i in all_inv if i.payment_status == 'Paid')
    pending_count = sum(1 for i in all_inv if i.payment_status == 'Pending')
    overdue_count = sum(1 for i in all_inv if i.payment_status == 'Overdue')
    partial_count = sum(1 for i in all_inv if i.payment_status == 'Partially Paid')
    total_revenue = sum(i.grand_total for i in all_inv)
    total_paid = sum(i.paid_amount for i in all_inv)
    total_outstanding = sum(i.balance_due for i in all_inv)

    # Filter support
    q_search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = Invoice.query.order_by(Invoice.created_at.desc())

    if q_search:
        query = query.join(Customer, isouter=True).filter(
            db.or_(
                Invoice.invoice_number.ilike(f'%{q_search}%'),
                Invoice.reference_number.ilike(f'%{q_search}%'),
                Customer.name.ilike(f'%{q_search}%'),
            )
        )
    if status_filter:
        query = query.filter(Invoice.payment_status == status_filter)
    if date_from:
        d_from = _parse_form_date(date_from)
        if d_from:
            query = query.filter(Invoice.date >= d_from)
    if date_to:
        d_to = _parse_form_date(date_to)
        if d_to:
            query = query.filter(Invoice.date <= d_to)

    invoices = query.all()

    # Auto-update overdue status
    updated = False
    for inv in invoices:
        if inv.is_overdue and inv.payment_status == 'Pending':
            inv.payment_status = 'Overdue'
            updated = True
    if updated:
        db.session.commit()

    return render_template('invoices/index.html',
        invoices=invoices,
        total_count=total_count,
        paid_count=paid_count,
        pending_count=pending_count,
        overdue_count=overdue_count,
        partial_count=partial_count,
        total_revenue=total_revenue,
        total_paid=total_paid,
        total_outstanding=total_outstanding,
        q_search=q_search,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@invoices_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    customers = Customer.query.order_by(Customer.name).all()
    company = CompanySettings.query.first()

    if request.method == 'POST':
        inv = Invoice(
            invoice_number=generate_invoice_number(),
        )
        db.session.add(inv)
        db.session.flush()  # get inv.id before adding items
        _build_invoice_from_form(inv, request.form, is_edit=False)
        db.session.commit()
        flash(f'Invoice {inv.invoice_number} created successfully!', 'success')
        return redirect(url_for('invoices.view', id=inv.id))

    today_str = date.today().strftime('%Y-%m-%d')
    next_inv_num = generate_invoice_number()
    return render_template('invoices/create.html',
        customers=customers, company=company,
        today_str=today_str, next_inv_num=next_inv_num)


@invoices_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    inv = db.get_or_404(Invoice, id)
    customers = Customer.query.order_by(Customer.name).all()
    company = CompanySettings.query.first()

    if request.method == 'POST':
        _build_invoice_from_form(inv, request.form, is_edit=True)
        db.session.commit()
        flash(f'Invoice {inv.invoice_number} updated successfully!', 'success')
        return redirect(url_for('invoices.view', id=inv.id))

    return render_template('invoices/edit.html',
        inv=inv, customers=customers, company=company)


@invoices_bp.route('/view/<int:id>')
@login_required
def view(id):
    inv = db.get_or_404(Invoice, id)
    company = CompanySettings.query.first()
    return render_template('invoices/view.html', inv=inv, company=company, now=date.today())


@invoices_bp.route('/duplicate/<int:id>', methods=['POST'])
@login_required
def duplicate(id):
    orig = db.get_or_404(Invoice, id)
    new_inv = Invoice(
        invoice_number=generate_invoice_number(),
        date=date.today(),
        due_date=orig.due_date,
        reference_number=orig.reference_number,
        customer_id=orig.customer_id,
        discount_type=orig.discount_type,
        discount_value=orig.discount_value,
        discount_amount=orig.discount_amount,
        sub_total=orig.sub_total,
        cgst_total=orig.cgst_total,
        sgst_total=orig.sgst_total,
        igst_total=orig.igst_total,
        installation_qty=orig.installation_qty,
        installation_rate=orig.installation_rate,
        installation_charges=orig.installation_charges,
        wiring_charges=orig.wiring_charges,
        transport_charges=orig.transport_charges,
        grand_total=orig.grand_total,
        paid_amount=0.0,
        balance_due=orig.grand_total,
        payment_status='Pending',
        payment_method=orig.payment_method,
        notes=orig.notes,
        terms_conditions=orig.terms_conditions,
    )
    db.session.add(new_inv)
    db.session.flush()
    for item in orig.items:
        db.session.add(InvoiceItem(
            invoice_id=new_inv.id,
            product_id=item.product_id,
            name=item.name,
            description=item.description,
            hsn_code=item.hsn_code,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            gst_percent=item.gst_percent,
            taxable_value=item.taxable_value,
            tax_amount=item.tax_amount,
            line_total=item.line_total,
        ))
    db.session.commit()
    flash(f'Invoice duplicated as {new_inv.invoice_number}', 'success')
    return redirect(url_for('invoices.edit', id=new_inv.id))


@invoices_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    inv = db.get_or_404(Invoice, id)
    db.session.delete(inv)
    db.session.commit()
    flash('Invoice deleted successfully', 'success')
    return redirect(url_for('invoices.index'))


@invoices_bp.route('/payment/<int:id>', methods=['POST'])
@login_required
def record_payment(id):
    inv = db.get_or_404(Invoice, id)
    amount = _safe_float(request.form.get('amount'), 0.0)
    if amount <= 0:
        flash('Payment amount must be greater than zero.', 'danger')
        return redirect(url_for('invoices.view', id=id))
    if amount > inv.balance_due + 0.01:
        flash(f'Payment amount (₹{amount:,.2f}) exceeds balance due (₹{inv.balance_due:,.2f}).', 'danger')
        return redirect(url_for('invoices.view', id=id))

    pmt = InvoicePayment(
        invoice_id=inv.id,
        amount=round(amount, 2),
        payment_date=_parse_form_date(request.form.get('payment_date'), default=date.today()),
        payment_method=request.form.get('payment_method', '').strip(),
        reference_number=request.form.get('reference_number', '').strip(),
        notes=request.form.get('notes', '').strip(),
    )
    db.session.add(pmt)
    db.session.flush()
    inv.recalculate_balance()
    db.session.commit()
    flash(f'Payment of ₹{amount:,.2f} recorded. Balance due: ₹{inv.balance_due:,.2f}', 'success')
    return redirect(url_for('invoices.view', id=id))


@invoices_bp.route('/payment/delete/<int:pmt_id>', methods=['POST'])
@login_required
def delete_payment(pmt_id):
    pmt = db.get_or_404(InvoicePayment, pmt_id)
    inv_id = pmt.invoice_id
    inv = db.get_or_404(Invoice, inv_id)
    db.session.delete(pmt)
    db.session.flush()
    inv.recalculate_balance()
    db.session.commit()
    flash('Payment entry removed.', 'success')
    return redirect(url_for('invoices.view', id=inv_id))


@invoices_bp.route('/preview/<int:id>')
@login_required
def preview(id):
    from utils.pdf_generator import render_invoice_html
    inv = db.get_or_404(Invoice, id)
    company = CompanySettings.query.first()
    html = render_invoice_html(inv, company)
    return Response(html, mimetype='text/html')


@invoices_bp.route('/pdf/<int:id>')
@invoices_bp.route('/download_pdf/<int:id>')
@login_required
def download_pdf(id):
    from utils.pdf_generator import generate_invoice_pdf
    inv = db.get_or_404(Invoice, id)
    company = CompanySettings.query.first()
    pdf_path = generate_invoice_pdf(inv, company)
    cust_name = inv.customer.name if inv.customer else 'Customer'
    safe_name = "".join(c for c in cust_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    inv_date_str = inv.date.strftime('%Y-%m-%d') if inv.date else date.today().strftime('%Y-%m-%d')
    safe_inv = (inv.invoice_number or 'INV').replace('-', '_')
    return send_file(pdf_path, as_attachment=True,
                     download_name=f"INVOICE_{safe_inv}_{safe_name}_{inv_date_str}.pdf")
