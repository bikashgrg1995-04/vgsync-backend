import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Staff, Supplier, Stock


DISCOUNT_PERCENTAGE = 20  # 🔥 backend controlled fixed discount


@transaction.atomic
def upload_purchase_excel(file, user):

    df = pd.read_excel(file)

    required_cols = [
        'purchase_ref',
        'supplier',
        'date',
        'item_no',
        'quantity',
        'price',
        'staff_id'
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    grouped = df.groupby("purchase_ref")

    created = []
    errors = []

    for ref, rows in grouped:
        try:
            first_row = rows.iloc[0]

            # ---------------- Supplier ----------------
            supplier = Supplier.objects.get(
                name__iexact=str(first_row['supplier']).strip()
            )

            # ---------------- Staff ----------------
            staff = None
            if not pd.isna(first_row['staff_id']):
                try:
                    staff = Staff.objects.get(id=int(first_row['staff_id']))
                except Staff.DoesNotExist:
                    staff = None

            # =====================================================
            # 🔥 Pre-calculate totals BEFORE creating items
            # (signal fires on each PurchaseItem.create and
            #  overwrites net_total using after_discount + vat,
            #  so those fields must exist on the purchase first)
            # =====================================================
            grand_total = sum(
                int(row['quantity']) * float(row['price'])
                for _, row in rows.iterrows()
            )

            discount_percentage  = DISCOUNT_PERCENTAGE
            discount_amount      = round(grand_total * discount_percentage / 100, 2)
            after_discount_amount = grand_total - discount_amount
            vat_amount           = round(after_discount_amount * 0.13, 2)
            net_total            = round(after_discount_amount + vat_amount, 2)
            remaining_amount     = net_total  # paid_amount = 0

            # ---------------- Create Purchase ----------------
            purchase = Purchase.objects.create(
                supplier=supplier,
                date=first_row['date'],
                created_by=staff,
                is_migrated=True,
                grand_total=grand_total,
                discount_percentage=discount_percentage,
                discount_amount=discount_amount,
                after_discount_amount=after_discount_amount,
                vat_amount=vat_amount,
                net_total=net_total,
                paid_amount=0,
                remaining_amount=remaining_amount,
                status="pending"
            )

            # ---------------- Create Items (signals update stock) ----------------
            # NOTE: bulk_create does NOT fire post_save signals,
            # so we use individual create() to trigger stock adjustment.
            # The signal also overwrites net_total = after_discount + vat,
            # which is already correct on the purchase object — so it's safe.
            for _, row in rows.iterrows():
                stock_item = Stock.objects.get(
                    item_no__iexact=str(row['item_no']).strip()
                )
                PurchaseItem.objects.create(
                    purchase=purchase,
                    item=stock_item,
                    quantity=int(row['quantity']),
                    price=float(row['price']),
                )

            # ---------------- Restore net_total after signal ----------------
            # Signal recalculates net_total from after_discount + vat on each
            # PurchaseItem save. The final value should match our calculation,
            # but we refresh and explicitly save to be safe.
            purchase.refresh_from_db()
            purchase.net_total = net_total
            purchase.save(update_fields=['net_total'])

            created.append({
                "purchase_id": purchase.id,
                "purchase_ref": ref,
                "grand_total": grand_total,
                "discount_percentage": discount_percentage,
                "discount_amount": discount_amount,
                "net_total": net_total
            })

        except Exception as e:
            errors.append({
                "purchase_ref": ref,
                "error": str(e)
            })

    return {
        "success": len(created),
        "failed": len(errors),
        "created_purchases": created,
        "errors": errors
    }