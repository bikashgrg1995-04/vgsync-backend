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
    """Safely parse datetime/date from Excel/str/NaN"""
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

# ---------- MAIN FUNCTION ----------
def upload_sales_excel(file):
    df = pd.read_excel(file)

    required = ['sale_ref', 'sale_date', 'item_no', 'quantity', 'rate']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    grouped = df.groupby('sale_ref')

    created_sales = []
    errors = []

    for sale_ref, rows in grouped:
        try:
            with transaction.atomic():
                first = rows.iloc[0]

                # Service vs Stock sale
                is_servicing = parse_bool(first.get('is_servicing'))

                # handled_by (optional)
                handled_by = None
                if not is_nan(first.get('handled_by')):
                    try:
                        handled_by = Staff.objects.get(pk=int(first['handled_by']))
                    except Staff.DoesNotExist:
                        handled_by = None

                # ---------- CREATE SALE ----------
                if is_servicing:
                    sale = Sale.objects.create(
                        sale_date=parse_dt(first.get('sale_date')) or timezone.now(),
                        customer_name=str(clean(first.get('customer_name')) or '').strip(),
                        contact_no=clean(first.get('contact_no')),
                        vehicle_model=clean(first.get('vehicle_model')),
                        is_servicing=True,
                        km_driven=clean(first.get('km_driven')),
                        job_card_no=clean(first.get('job_card_no')),
                        bike_registration_no=clean(first.get('bike_registration_no')),
                        vehicle_color=clean(first.get('vehicle_color')),
                        received_date=parse_dt(first.get('received_date')),
                        delivery_date=parse_dt(first.get('delivery_date')),
                        bill_no=clean(first.get('bill_no')),
                        technician_name=clean(first.get('technician_name')),
                        is_free_servicing=parse_bool(first.get('is_free_servicing')),
                        is_repair_job=parse_bool(first.get('is_repair_job')),
                        is_accident=parse_bool(first.get('is_accident')),
                        is_warranty_job=parse_bool(first.get('is_warrenty_job')),
                        follow_up_date=parse_dt(first.get('follow_up_date')),
                        post_service_feedback_date=parse_dt(first.get('post_service_feedback_date')),
                        job_done_on_vehicle=clean(first.get('job_done_on_vehicle')),
                        remarks=clean(first.get('remarks')),
                        labour_charge=float(clean(first.get('labour_charge')) or 0),
                        paid_amount=float(clean(first.get('paid_amount')) or 0),
                        paid_from=clean(first.get('paid_from')),
                        handled_by=handled_by,
                        is_paid=clean(first.get('is_paid')) or 'not_paid',
                        is_migrated=True,
                    )
                else:
                    # Stock sale: ignore service fields
                    sale = Sale.objects.create(
                        sale_date=parse_dt(first.get('sale_date')) or timezone.now(),
                        customer_name=str(clean(first.get('customer_name')) or '').strip(),
                        contact_no=clean(first.get('contact_no')),
                        vehicle_model=clean(first.get('vehicle_model')),
                        is_servicing=False,
                        labour_charge=float(clean(first.get('labour_charge')) or 0),
                        paid_amount=float(clean(first.get('paid_amount')) or 0),
                        paid_from=clean(first.get('paid_from')),
                        handled_by=handled_by,
                        is_paid=clean(first.get('is_paid')) or 'not_paid',
                        is_migrated=True,
                    )

                # ---------- CREATE SALE ITEMS ----------
                for _, r in rows.iterrows():
                    item_no = str(r['item_no']).strip().upper()
                    stock = Stock.objects.get(item_no=item_no)

                    SaleItem.objects.create(
                        sale=sale,
                        item=stock,
                        quantity=int(clean(r.get('quantity')) or 0),
                        price=float(clean(r.get('rate')) or 0),
                    )

                # Save to trigger totals, remaining_amount, and signals
                sale.save()
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
