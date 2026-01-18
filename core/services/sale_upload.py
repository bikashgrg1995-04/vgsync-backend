import pandas as pd
import math
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from core.models import Sale, SaleItem, Stock, Staff

# ---------- HELPERS ----------
def is_nan(val):
    return val is None or (isinstance(val, float) and math.isnan(val))

def clean(val):
    return None if is_nan(val) else val

def parse_bool(val):
    if is_nan(val):
        return False
    return str(val).strip().lower() in ['true', '1', 'yes']

def parse_dt(val):
    if is_nan(val):
        return None
    dt = val
    if isinstance(val, str):
        dt = parse_datetime(val) or parse_date(val)
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    if hasattr(dt, "date") and not isinstance(dt, pd.Timestamp):
        return dt.date()
    return dt

# ---------- Sale Totals Helper ----------
def calculate_sale_totals(sale: Sale):
    items = sale.items.all()
    total = sum(item.quantity * item.sale_price for item in items)
    total += sale.labour_charge or 0
    sale.grand_total = total
    sale.net_total = total  # apply discounts if needed
    sale.remaining_amount = max(total - (sale.paid_amount or 0), 0)
    sale.save(update_fields=['grand_total', 'net_total', 'remaining_amount'])

# ---------- MAIN FUNCTION ----------
def upload_sales_excel(file):
    df = pd.read_excel(file)

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

                # Determine service vs stock sale
                is_servicing = parse_bool(first.get('is_servicing'))

                # handled_by (optional)
                handled_by = None
                if not is_nan(first.get('handled_by')):
                    try:
                        handled_by = Staff.objects.get(pk=int(first['handled_by']))
                    except Staff.DoesNotExist:
                        handled_by = None

                # ---------- CREATE SALE ----------
                sale = Sale.objects.create(
                    sale_date=parse_dt(first.get('sale_date')) or timezone.now(),
                    customer_name=str(clean(first.get('customer_name')) or '').strip(),
                    contact_no=clean(first.get('contact_no')),
                    vehicle_model=clean(first.get('vehicle_model')),
                    is_servicing=is_servicing,
                    km_driven=clean(first.get('km_driven')) if is_servicing else None,
                    job_card_no=clean(first.get('job_card_no')) if is_servicing else None,
                    bike_registration_no=clean(first.get('bike_registration_no')) if is_servicing else None,
                    vehicle_type = clean(first.get('vehicle_type')) if is_servicing else None,
                    vehicle_color=clean(first.get('vehicle_color')) if is_servicing else None,
                    received_date=parse_dt(first.get('received_date')) if is_servicing else None,
                    delivery_date=parse_dt(first.get('delivery_date')) if is_servicing else None,
                    bill_no=clean(first.get('bill_no')),
                    technician_name=clean(first.get('technician_name')) if is_servicing else None,
                    is_free_servicing=parse_bool(first.get('is_free_servicing')) if is_servicing else False,
                    is_repair_job=parse_bool(first.get('is_repair_job')) if is_servicing else False,
                    is_accident=parse_bool(first.get('is_accident')) if is_servicing else False,
                    is_warranty_job=parse_bool(first.get('is_warrenty_job')) if is_servicing else False,
                    follow_up_date=parse_dt(first.get('follow_up_date')) if is_servicing else None,
                    post_service_feedback_date=parse_dt(first.get('post_service_feedback_date')) if is_servicing else None,
                    job_done_on_vehicle=clean(first.get('job_done_on_vehicle')) if is_servicing else None,
                    remarks=clean(first.get('remarks')),
                    labour_charge=float(clean(first.get('labour_charge')) or 0),
                    paid_amount=float(clean(first.get('paid_amount')) or 0),
                    paid_from=clean(first.get('paid_from')),
                    handled_by=handled_by,
                    is_paid=clean(first.get('is_paid')) or 'not_paid',
                    is_migrated=True,
                )

                # ---------- CREATE SALE ITEMS ----------
                sale_items = []
                for idx, r in rows.iterrows():
                    try:
                        item_no = str(r['item_no']).strip().upper()
                        stock = Stock.objects.get(item_no=item_no)
                        quantity = int(clean(r.get('quantity')) or 0)
                        rate = float(clean(r.get('rate')) or stock.sale_price)

                        sale_items.append(
                            SaleItem(
                                sale=sale,
                                item=stock,
                                quantity=quantity,
                                sale_price=rate,
                                total_price=quantity * rate
                            )
                        )

                        # Adjust stock only for non-service sale
                        if not sale.is_servicing:
                            stock.adjust_stock(-quantity)

                    except Stock.DoesNotExist:
                        raise ValueError(f"Row {idx + 2}: Item with item_no '{r['item_no']}' does not exist.")
                    except Exception as e:
                        raise ValueError(f"Row {idx + 2}: {str(e)}")

                SaleItem.objects.bulk_create(sale_items)

                # ---------- CALCULATE TOTALS ----------
                calculate_sale_totals(sale)

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
