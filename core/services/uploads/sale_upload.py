import pandas as pd
import math
from django.db import transaction
from django.utils import timezone
from core.models import Sale, SaleItem, Stock, Staff

# ---------- HELPERS ----------
def is_nan(val):
    return val is None or (isinstance(val, float) and math.isnan(val))

def clean(val):
    if isinstance(val, str):
        val = val.strip()
    return None if is_nan(val) or val == '' else val

def parse_bool(val):
    if is_nan(val):
        return False
    return str(val).strip().lower() in ['true', '1', 'yes']

def parse_dt(val):
    if is_nan(val) or val == '':
        return None
    if isinstance(val, pd.Timestamp):
        val = val.to_pydatetime()
    elif isinstance(val, str):
        try:
            val = pd.to_datetime(val, errors='coerce')
        except:
            return None
    if hasattr(val, "tzinfo") and val.tzinfo is None:
        val = timezone.make_aware(val)
    return val

def calculate_sale_totals(sale: Sale):
    items = sale.items.all()
    total = sum(item.quantity * item.sale_price for item in items)
    total += sale.labour_charge or 0
    sale.grand_total = total
    sale.net_total = total
    sale.remaining_amount = max(total - (sale.paid_amount or 0), 0)
    sale.save(update_fields=['grand_total', 'net_total', 'remaining_amount'])

def update_paid_status(sale: Sale):
    if sale.paid_amount >= sale.net_total:
        sale.is_paid = 'paid'
    elif sale.paid_amount > 0:
        sale.is_paid = 'partial'
    else:
        sale.is_paid = 'not_paid'
    sale.save(update_fields=['is_paid'])

# ---------- MAIN FUNCTION ----------
def upload_sales_excel(file):
    df = pd.read_excel(file)
    
    # Strip column names to remove hidden spaces
    df.columns = df.columns.str.strip()
    
    required = ['sale_ref', 'sale_date', 'item_no', 'quantity', 'rate']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    grouped = df.groupby('sale_ref')
    created_sales = []
    errors = []

    for sale_ref, rows in grouped:
        try:
            with transaction.atomic():
                first = rows.iloc[0]

                is_servicing = parse_bool(first.get('is_servicing'))
                is_migrated = parse_bool(first.get('is_migrated'))

                # handled_by
                handled_by = None
                staff_val = clean(first.get('handled_by'))
                if staff_val:
                    try:
                        handled_by = Staff.objects.get(pk=int(staff_val))
                    except Staff.DoesNotExist:
                        handled_by = None

                # ---------- CREATE SALE ----------
                sale = Sale.objects.create(
                    sale_date=parse_dt(first.get('sale_date')) or timezone.now(),
                    customer_name=str(clean(first.get('customer_name')) or ''),
                    contact_no=str(clean(first.get('contact_no') or '')).strip(),
                    vehicle_model=clean(first.get('vehicle_model')),
                    is_servicing=is_servicing,
                    km_driven=int(clean(first.get('km_driven') or 0)) if is_servicing else None,
                    job_card_no=clean(first.get('job_card_no')) if is_servicing else None,
                    bike_registration_no=clean(first.get('bike_registration_no')) if is_servicing else None,
                    vehicle_type=clean(first.get('vehicle_type')) if is_servicing else None,
                    vehicle_color=clean(first.get('vehicle_color')) if is_servicing else None,
                    received_date=parse_dt(first.get('received_date')) if is_servicing else None,
                    delivery_date=parse_dt(first.get('delivery_date')) if is_servicing else None,
                    bill_no=clean(first.get('bill_no')),
                    technician_name=clean(first.get('technician_name')) if is_servicing else None,
                    is_free_servicing=parse_bool(first.get('is_free_servicing')) if is_servicing else False,
                    is_repair_job=parse_bool(first.get('is_repair_job')) if is_servicing else False,
                    is_accident=parse_bool(first.get('is_accident')) if is_servicing else False,
                    is_warranty_job=parse_bool(first.get('is_warranty_job')) if is_servicing else False,
                    follow_up_date=parse_dt(first.get('follow_up_date')) if is_servicing else None,
                    post_service_feedback_date=parse_dt(first.get('post_service_feedback_date')) if is_servicing else None,
                    job_done_on_vehicle=clean(first.get('job_done_on_vehicle')) if is_servicing else None,
                    remarks=clean(first.get('remarks')),
                    labour_charge=float(clean(first.get('labour_charge') or 0)) if is_servicing else 0,
                    paid_amount=float(clean(first.get('paid_amount') or 0)),
                    paid_from=clean(first.get('paid_from')),
                    handled_by=handled_by,
                    is_paid='not_paid',
                    is_migrated=is_migrated,
                )

                # ---------- CREATE SALE ITEMS ----------
                sale_items = []
                for idx, r in rows.iterrows():
                    item_no = str(r['item_no']).strip().upper()
                    try:
                        stock = Stock.objects.get(item_no=item_no)
                    except Stock.DoesNotExist:
                        raise ValueError(f"Row {idx + 2}: Item_no '{item_no}' does not exist.")

                    quantity = int(clean(r.get('quantity') or 0))

                    rate_val = r.get('rate')
                    if is_nan(rate_val) or rate_val is None:
                        if stock.sale_price is None:
                            raise ValueError(f"Row {idx + 2}: No rate specified and Stock.sale_price empty for item {item_no}")
                        rate = stock.sale_price
                    else:
                        rate = float(rate_val)

                    sale_items.append(
                        SaleItem(
                            sale=sale,
                            item=stock,
                            quantity=quantity,
                            sale_price=rate,
                            total_price=quantity * rate
                        )
                    )

                SaleItem.objects.bulk_create(sale_items)

                # ---------- CALCULATE TOTALS ----------
                calculate_sale_totals(sale)
                update_paid_status(sale)

                created_sales.append(sale.id)

        except Exception as e:
            errors.append({
                "sale_ref": sale_ref,
                "error": str(e)
            })

    return {
        "created_sales": created_sales,
        "errors": errors
    }
