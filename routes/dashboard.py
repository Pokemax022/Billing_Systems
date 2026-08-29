from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from models.quotation import Quotation, QuotationItem
from models.customer import Customer
from models.product import Product
from database.db import db
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

def _non_gst_revenue(q):
    if not q:
        return 0.0
    return ((q.sub_total or 0.0) +
            (q.installation_charges or 0.0) +
            (q.wiring_charges or 0.0) +
            (q.transport_charges or 0.0))

def _profit_for(q):
    """Return gross profit for a quotation (selling - dealer cost) using non-GST base prices."""
    if not q:
        return 0.0
    return _non_gst_revenue(q) - (q.total_dealer_cost or 0.0)

def _margin_for(q):
    """Return profit margin % for a quotation."""
    rev = _non_gst_revenue(q)
    if rev > 0:
        return round((_profit_for(q) / rev) * 100, 1)
    return 0.0

def _margin_badge(margin):
    if margin >= 20:
        return 'high'
    elif margin >= 10:
        return 'medium'
    else:
        return 'low'

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    today = date.today()
    this_month = today.month
    this_year  = today.year

    total_quotations = Quotation.query.count()
    total_customers  = Customer.query.count()
    total_products   = Product.query.count()

    # Revenue & profit using non-GST base prices
    all_quotes = Quotation.query.all()
    revenue = sum(_non_gst_revenue(q) for q in all_quotes)
    total_dealer_cost = sum(q.total_dealer_cost for q in all_quotes)
    profit = revenue - total_dealer_cost
    avg_margin = round((profit / revenue * 100), 1) if revenue > 0 else 0.0

    # Today
    today_quotes  = Quotation.query.filter(Quotation.date == today).all()
    today_profit  = sum(_profit_for(q) for q in today_quotes)

    # Monthly
    monthly_quotes = Quotation.query.filter(
        extract('month', Quotation.date) == this_month,
        extract('year',  Quotation.date) == this_year
    ).all()
    monthly_profit  = sum(_profit_for(q) for q in monthly_quotes)
    monthly_revenue = sum(_non_gst_revenue(q) for q in monthly_quotes)

    # Low margin (< 10%)
    low_margin_quotes = [q for q in all_quotes if _margin_for(q) < 10 and _non_gst_revenue(q) > 0]

    # Best customer by revenue
    from collections import defaultdict
    cust_rev = defaultdict(float)
    for q in all_quotes:
        if q.customer:
            cust_rev[q.customer.name] += _non_gst_revenue(q)
    best_customer = max(cust_rev, key=cust_rev.get) if cust_rev else 'N/A'
    best_customer_rev = cust_rev.get(best_customer, 0)

    # Most profitable quotation
    if all_quotes:
        best_quote = max(all_quotes, key=lambda q: _profit_for(q))
        best_quote_profit = _profit_for(best_quote)
    else:
        best_quote = None
        best_quote_profit = 0

    # Recent quotations with profit data (last 10)
    recent_quotes = Quotation.query.order_by(Quotation.created_at.desc()).limit(10).all()
    recent_data = []
    for q in recent_quotes:
        p = _profit_for(q)
        m = _margin_for(q)
        r = _non_gst_revenue(q)
        recent_data.append({
            'q': q,
            'revenue': r,
            'profit': p,
            'margin': m,
            'badge': _margin_badge(m)
        })

    # Monthly chart data (last 6 months)
    monthly_chart = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=i*30)
        m_quotes = Quotation.query.filter(
            extract('month', Quotation.date) == d.month,
            extract('year',  Quotation.date) == d.year
        ).all()
        monthly_chart.append({
            'label': d.strftime('%b %Y'),
            'revenue': round(sum(_non_gst_revenue(q) for q in m_quotes), 2),
            'profit':  round(sum(_profit_for(q) for q in m_quotes), 2),
        })

    # Top 5 profitable quotations for bar chart
    top_quotes = sorted(all_quotes, key=lambda q: _profit_for(q), reverse=True)[:5]
    top_chart = [{'label': q.quotation_number, 'profit': round(_profit_for(q), 2)} for q in top_quotes]

    # Top products
    from collections import Counter
    prod_qty = Counter()
    for q in all_quotes:
        for item in q.items:
            prod_qty[item.name] += item.quantity
    top_products = prod_qty.most_common(5)

    return render_template('dashboard.html',
        total_quotations=total_quotations,
        total_customers=total_customers,
        total_products=total_products,
        revenue=revenue,
        profit=profit,
        avg_margin=avg_margin,
        today_profit=today_profit,
        monthly_profit=monthly_profit,
        monthly_revenue=monthly_revenue,
        low_margin_count=len(low_margin_quotes),
        best_customer=best_customer,
        best_customer_rev=best_customer_rev,
        best_quote=best_quote,
        best_quote_profit=best_quote_profit,
        recent_data=recent_data,
        monthly_chart=monthly_chart,
        top_chart=top_chart,
        top_products=top_products,
    )


@dashboard_bp.route('/api/quotation-profit/<int:id>')
@login_required
def api_quotation_profit(id):
    """Return internal profit breakdown for a single quotation (JSON)."""
    q = db.get_or_404(Quotation, id)
    gross_profit = _profit_for(q)
    margin = _margin_for(q)
    gst_collected = (q.cgst_total or 0.0) + (q.sgst_total or 0.0) + (q.igst_total or 0.0)

    items_data = []
    for item in q.items:
        sp = item.selling_price or 0.0
        dp = item.dealer_price or 0.0
        qty = item.quantity or 1
        taxable = item.taxable_value or (qty * sp)
        item_profit = (sp - dp) * qty
        item_margin = round((item_profit / taxable * 100), 1) if taxable > 0 else 0.0
        items_data.append({
            'name': item.name or 'Item',
            'hsn_code': item.hsn_code or '-',
            'quantity': qty,
            'dealer_price': dp,
            'selling_price': sp,
            'taxable_value': taxable,
            'item_profit': round(item_profit, 2),
            'item_margin': item_margin,
        })

    return jsonify({
        'quotation_number': q.quotation_number or 'Quotation',
        'customer': q.customer.name if q.customer else 'N/A',
        'date': q.date.strftime('%d/%m/%Y') if q.date else 'N/A',
        'grand_total': q.grand_total or 0.0,
        'revenue_ex_gst': _non_gst_revenue(q),
        'dealer_cost': q.total_dealer_cost or 0.0,
        'gross_profit': round(gross_profit, 2),
        'margin': margin,
        'gst_collected': round(gst_collected, 2),
        'installation_charges': q.installation_charges or 0.0,
        'status': q.status or 'Draft',
        'payment_status': q.payment_status or 'Unpaid',
        'items': items_data,
    })
