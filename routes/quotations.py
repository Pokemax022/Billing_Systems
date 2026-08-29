import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, Response
from flask_login import login_required
from models.quotation import Quotation, QuotationItem
from models.customer import Customer
from models.product import Product
from models.company import CompanySettings
from database.db import db
from utils.pdf_generator import generate_quotation_pdf, render_quotation_html

quotations_bp = Blueprint('quotations', __name__, url_prefix='/quotations')

def _safe_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        import re
        clean = re.sub(r'[^\d\.-]', '', str(val))
        return float(clean) if clean else default
    except (ValueError, TypeError):
        return default

def _safe_int(val, default=0):
    if val is None or val == '':
        return default
    try:
        import re
        clean = re.sub(r'[^\d-]', '', str(val))
        return int(float(clean)) if clean else default
    except (ValueError, TypeError):
        return default

def generate_quotation_number():
    """Generate next unique quotation number like Q-1001, Q-1002 safely."""
    all_nums = []
    for q in Quotation.query.all():
        if q.quotation_number and '-' in q.quotation_number:
            try:
                all_nums.append(int(q.quotation_number.split('-')[-1]))
            except (IndexError, ValueError):
                pass
    start = max(all_nums, default=1000) + 1
    candidate = f"Q-{start:04d}"
    while Quotation.query.filter_by(quotation_number=candidate).first():
        start += 1
        candidate = f"Q-{start:04d}"
    return candidate

@quotations_bp.route('/')
@login_required
def index():
    quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()
    return render_template('quotations/index.html', quotations=quotations)

@quotations_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    customers = Customer.query.order_by(Customer.name).all()
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        
        # Charges — installation is price-per-point × number of points
        installation_rate = _safe_float(request.form.get('installation_charges'), 0.0)  # per-unit price
        installation_qty  = _safe_int(request.form.get('installation_qty'), 1)
        installation_charges = installation_rate * installation_qty               # total
        wiring_charges = _safe_float(request.form.get('wiring_charges'), 0.0)
        transport_charges = _safe_float(request.form.get('transport_charges'), 0.0)
        
        # Notes
        notes = request.form.get('notes')
        warranty_notes = request.form.get('warranty_notes')
        
        # Products array from dynamic form
        product_ids = request.form.getlist('product_id[]')
        product_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        selling_prices = request.form.getlist('selling_price[]')
        gst_percents = request.form.getlist('gst_percent[]')
        
        quote = Quotation(
            quotation_number=generate_quotation_number(),
            customer_id=customer_id if (customer_id and customer_id.isdigit()) else None,
            installation_rate=installation_rate,
            installation_qty=installation_qty,
            installation_charges=installation_charges,
            wiring_charges=wiring_charges,
            transport_charges=transport_charges,
            notes=notes,
            warranty_notes=warranty_notes
        )
        db.session.add(quote)
        db.session.flush() # Get quote ID
        
        sub_total = 0.0
        cgst_total = 0.0
        sgst_total = 0.0
        igst_total = 0.0
        total_dealer_cost = 0.0
        
        # Determine intra-state vs inter-state
        company = CompanySettings.query.first()
        customer = db.session.get(Customer, customer_id) if customer_id else None
        
        is_interstate = False
        if company and customer and company.gstin and customer.gst_number:
            if company.gstin[:2] != customer.gst_number[:2]:
                is_interstate = True
        elif customer and customer.gst_number and not customer.gst_number.startswith('24'):
            is_interstate = True
        
        from itertools import zip_longest
        for p_id, p_name, qty, sp, gst in zip_longest(product_ids, product_names, quantities, selling_prices, gst_percents, fillvalue=''):
            p = db.session.get(Product, int(p_id)) if (p_id and str(p_id).isdigit()) else None
            name = (p_name or '').strip()
            if not name and p:
                name = p.name
            if not name and not p:
                continue
                
            q = _safe_int(qty, 1)
            s_price = _safe_float(sp, 0.0)
            g_pct = _safe_float(gst, 18.0)
            
            taxable = q * s_price
            sub_total += taxable
            
            # Calculate ex-GST dealer price
            dp_ex_gst = (p.dealer_price / (1 + p.gst_percent / 100)) if (p and p.dealer_price) else 0.0
            total_dealer_cost += dp_ex_gst * q
            
            # Tax calculations
            tax_amt = taxable * (g_pct / 100)
            if is_interstate:
                igst_total += tax_amt
            else:
                cgst_total += tax_amt / 2
                sgst_total += tax_amt / 2
            
            item = QuotationItem(
                quotation_id=quote.id,
                product_id=p.id if p else None,
                name=name,
                hsn_code=p.hsn_code if p else "",
                quantity=q,
                dealer_price=dp_ex_gst,
                selling_price=s_price,
                gst_percent=g_pct,
                taxable_value=taxable
            )
            db.session.add(item)
        
        quote.sub_total = round(sub_total, 2)
        quote.cgst_total = round(cgst_total, 2)
        quote.sgst_total = round(sgst_total, 2)
        quote.igst_total = round(igst_total, 2)
        quote.total_dealer_cost = round(total_dealer_cost, 2)
        
        total_tax = quote.cgst_total + quote.sgst_total + quote.igst_total
        quote.grand_total = round(sub_total + total_tax + installation_charges + wiring_charges + transport_charges, 2)
        
        db.session.commit()
        flash('Quotation created successfully', 'success')
        return redirect(url_for('quotations.view', id=quote.id))
        
    return render_template('quotations/create.html', customers=customers)

@quotations_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    quote = db.get_or_404(Quotation, id)
    customers = Customer.query.order_by(Customer.name).all()
    
    if request.method == 'POST':
        cid = request.form.get('customer_id')
        quote.customer_id = int(cid) if (cid and str(cid).isdigit()) else None
        _inst_rate = _safe_float(request.form.get('installation_charges'), 0.0)  # per-unit
        _inst_qty  = _safe_int(request.form.get('installation_qty'), 1)
        quote.installation_rate     = _inst_rate
        quote.installation_qty      = _inst_qty
        quote.installation_charges  = _inst_rate * _inst_qty              # total
        quote.wiring_charges = _safe_float(request.form.get('wiring_charges'), 0.0)
        quote.transport_charges = _safe_float(request.form.get('transport_charges'), 0.0)
        quote.notes = request.form.get('notes')
        quote.warranty_notes = request.form.get('warranty_notes')
        
        # Clear existing items
        QuotationItem.query.filter_by(quotation_id=quote.id).delete()
        
        product_ids = request.form.getlist('product_id[]')
        product_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        selling_prices = request.form.getlist('selling_price[]')
        gst_percents = request.form.getlist('gst_percent[]')
        
        sub_total = 0.0
        cgst_total = 0.0
        sgst_total = 0.0
        igst_total = 0.0
        total_dealer_cost = 0.0
        
        company = CompanySettings.query.first()
        customer = db.session.get(Customer, quote.customer_id) if quote.customer_id else None
        
        is_interstate = False
        if company and customer and company.gstin and customer.gst_number:
            if company.gstin[:2] != customer.gst_number[:2]:
                is_interstate = True
        elif customer and customer.gst_number and not customer.gst_number.startswith('24'):
            is_interstate = True
            
        from itertools import zip_longest
        for p_id, p_name, qty, sp, gst in zip_longest(product_ids, product_names, quantities, selling_prices, gst_percents, fillvalue=''):
            p = db.session.get(Product, int(p_id)) if (p_id and str(p_id).isdigit()) else None
            name = (p_name or '').strip()
            if not name and p:
                name = p.name
            if not name and not p:
                continue
                
            q = _safe_int(qty, 1)
            s_price = _safe_float(sp, 0.0)
            g_pct = _safe_float(gst, 18.0)
            
            taxable = q * s_price
            sub_total += taxable
            
            # Calculate ex-GST dealer price
            dp_ex_gst = (p.dealer_price / (1 + p.gst_percent / 100)) if (p and p.dealer_price) else 0.0
            total_dealer_cost += dp_ex_gst * q
            
            tax_amt = taxable * (g_pct / 100)
            if is_interstate:
                igst_total += tax_amt
            else:
                cgst_total += tax_amt / 2
                sgst_total += tax_amt / 2
                
            item = QuotationItem(
                quotation_id=quote.id,
                product_id=p.id if p else None,
                name=name,
                hsn_code=p.hsn_code if p else "",
                quantity=q,
                dealer_price=dp_ex_gst,
                selling_price=s_price,
                gst_percent=g_pct,
                taxable_value=taxable
            )
            db.session.add(item)
            
        quote.sub_total = round(sub_total, 2)
        quote.cgst_total = round(cgst_total, 2)
        quote.sgst_total = round(sgst_total, 2)
        quote.igst_total = round(igst_total, 2)
        quote.total_dealer_cost = round(total_dealer_cost, 2)
        
        total_tax = quote.cgst_total + quote.sgst_total + quote.igst_total
        quote.grand_total = round(sub_total + total_tax + quote.installation_charges + quote.wiring_charges + quote.transport_charges, 2)
        
        db.session.commit()
        flash('Quotation updated successfully', 'success')
        return redirect(url_for('quotations.view', id=quote.id))
        
    return render_template('quotations/edit.html', quote=quote, customers=customers)

@quotations_bp.route('/view/<int:id>')
@login_required
def view(id):
    quote = db.get_or_404(Quotation, id)
    company = CompanySettings.query.first()
    return render_template('quotations/view.html', quote=quote, company=company)

@quotations_bp.route('/template/<int:id>')
@login_required
def select_template(id):
    """Show template selector page."""
    quote = db.get_or_404(Quotation, id)
    company = CompanySettings.query.first()
    return render_template('quotations/select_template.html', quote=quote, company=company)

@quotations_bp.route('/preview/<int:id>')
@login_required
def preview(id):
    """Render quotation HTML directly in browser for preview."""
    quote = db.get_or_404(Quotation, id)
    company = CompanySettings.query.first()
    template = request.args.get('template', 'premium')
    html = render_quotation_html(quote, company, template)
    return Response(html, mimetype='text/html')

@quotations_bp.route('/pdf/<int:id>')
@login_required
def download_pdf(id):
    quote = db.get_or_404(Quotation, id)
    company = CompanySettings.query.first()
    template = request.args.get('template', 'classic')
    
    pdf_path = generate_quotation_pdf(quote, company, template)
    
    cust_name = quote.customer.name if quote.customer else 'Customer'
    safe_name = "".join(c for c in cust_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    return send_file(pdf_path, as_attachment=True,
                     download_name=f"QUOTATION_{safe_name}_{quote.date}.pdf")

@quotations_bp.route('/public_pdf/<int:id>')
def public_pdf(id):
    """Publicly accessible PDF download/view for customer WhatsApp links."""
    quote = db.get_or_404(Quotation, id)
    company = CompanySettings.query.first()
    template = request.args.get('template', 'premium')
    
    pdf_path = generate_quotation_pdf(quote, company, template)
    cust_name = quote.customer.name if quote.customer else 'Customer'
    safe_name = "".join(c for c in cust_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    return send_file(pdf_path, as_attachment=False,
                     download_name=f"QUOTATION_{safe_name}_{quote.date}.pdf")

def clean_phone_for_whatsapp(phone, default_country='91'):
    """
    Sanitize and format phone number for WhatsApp Web.
    Strips non-digits, formats 10-digit Indian numbers with country code.
    """
    import re
    if not phone:
        return ''
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return ''
    if len(digits) == 10:
        return f"{default_country}{digits}"
    if len(digits) == 11 and digits.startswith('0'):
        return f"{default_country}{digits[1:]}"
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    return digits

def build_whatsapp_messages(quote, company):
    """Generate preset message templates for WhatsApp sharing."""
    cust_name = quote.customer.name if (quote.customer and quote.customer.name) else 'Customer'
    comp_name = company.name if (company and company.name) else 'MISTHI ENTERPRISE'
    comp_phone = company.mobile if (company and company.mobile) else ''
    comp_email = company.email if (company and company.email) else ''
    quote_num = quote.quotation_number or 'Quotation'
    quote_date = quote.date.strftime('%d/%m/%Y') if (quote and quote.date) else ''
    grand_total_num = (quote.grand_total or 0.0) if quote else 0.0
    total_val = f"₹{grand_total_num:,.2f}"
    items_count = len(quote.items or []) if quote else 0
    
    date_str = f" dated {quote_date}" if quote_date else ""
    date_line = f"• *Date:* {quote_date}\n" if quote_date else ""
    
    standard = (
        f"👋 *Dear {cust_name},*\n\n"
        f"Greetings from *{comp_name}*!\n\n"
        f"We are pleased to share our quotation for your CCTV & Security requirements.\n\n"
        f"📋 *Quotation Summary:*\n"
        f"• *Quotation No:* {quote_num}\n"
        f"{date_line}"
        f"• *Total Items:* {items_count}\n"
        f"• *Grand Total:* *{total_val}*\n\n"
        f"📎 *Note:* Please check the attached Quotation PDF document for the complete itemized pricing, technical specifications, and terms.\n\n"
        f"If you have any questions or need modifications, feel free to contact us!\n\n"
        f"Best regards,\n"
        f"*{comp_name}*\n"
        f"📞 {comp_phone}\n"
        f"✉️ {comp_email}"
    )
    
    short = (
        f"Hello {cust_name},\n\n"
        f"Please find attached Quotation *{quote_num}*{date_str} from *{comp_name}* for *{total_val}*.\n\n"
        f"Please review the attached PDF and let us know your feedback.\n\n"
        f"Thank you,\n*{comp_name}* ({comp_phone})"
    )
    
    followup = (
        f"Dear {cust_name},\n\n"
        f"Following up on our discussion, here is the official quotation *{quote_num}* for *{total_val}* from *{comp_name}*.\n\n"
        f"Please review the attached PDF document for complete details. We are ready to proceed once approved.\n\n"
        f"Regards,\n*{comp_name}* | {comp_phone}"
    )
    
    return {
        'standard': standard,
        'short': short,
        'followup': followup
    }

@quotations_bp.route('/whatsapp')
@quotations_bp.route('/whatsapp/<int:id>')
@login_required
def whatsapp_menu(id=None):
    """Dedicated WhatsApp Quotations Hub and Sending Menu."""
    # Allow id from route parameter or query parameter '?id='
    quote_id = id or request.args.get('id', type=int)
    
    all_quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()
    company = CompanySettings.query.first()
    
    selected_quote = None
    clean_phone = ''
    raw_phone = ''
    messages = {}
    
    if quote_id:
        selected_quote = db.session.get(Quotation, quote_id)
        if selected_quote:
            raw_phone = selected_quote.customer.mobile if (selected_quote.customer and selected_quote.customer.mobile) else ''
            clean_phone = clean_phone_for_whatsapp(raw_phone)
            messages = build_whatsapp_messages(selected_quote, company)
    elif all_quotations:
        # Default to most recent quotation if none explicitly selected
        selected_quote = all_quotations[0]
        raw_phone = selected_quote.customer.mobile if (selected_quote.customer and selected_quote.customer.mobile) else ''
        clean_phone = clean_phone_for_whatsapp(raw_phone)
        messages = build_whatsapp_messages(selected_quote, company)

    selected_template = request.args.get('template', 'premium')

    return render_template(
        'quotations/whatsapp.html',
        quotations=all_quotations,
        quote=selected_quote,
        company=company,
        clean_phone=clean_phone,
        raw_phone=raw_phone,
        messages=messages,
        selected_template=selected_template
    )

@quotations_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    quote = db.get_or_404(Quotation, id)
    db.session.delete(quote)
    db.session.commit()
    flash('Quotation deleted successfully', 'success')
    return redirect(url_for('quotations.index'))
