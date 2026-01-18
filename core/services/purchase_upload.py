import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Staff, Supplier, Stock


@transaction.atomic
def upload_purchase_excel(file, user):
    df = pd.read_excel(file)

    required_cols = ['purchase_ref', 'supplier', 'date', 'item_no', 'quantity', 'price']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    grouped = df.groupby("purchase_ref")
    created, errors = [], []

    for ref, rows in grouped:
        try:
            # ---------------- Supplier ----------------
            supplier = Supplier.objects.get(name=rows.iloc[0]['supplier'])

            # ---------------- Staff ----------------
            staff = getattr(user, 'staff', None)
            if not staff:
                staff, _ = Staff.objects.get_or_create(
                    name=f"Imported by {user.username}",
                    email=user.email
                )

            # ---------------- Purchase ----------------
            purchase = Purchase.objects.create(
                supplier=supplier,
                date=rows.iloc[0]['date'],
                created_by=staff,
                is_migrated=True   # Important to prevent stock update signals
            )

            items = []
            net_total = 0

            # ---------------- Items ----------------
            for _, row in rows.iterrows():
                item = Stock.objects.get(item_no=row['item_no'])

                qty = int(row['quantity'])
                price = float(row['price'])

                net_total += qty * price  # <-- Only use purchase price

                items.append(
                    PurchaseItem(
                        purchase=purchase,
                        item=item,
                        quantity=qty,
                        price=price
                    )
                )

            PurchaseItem.objects.bulk_create(items)

            # ---------------- Discount (Purchase level) ----------------
            discount = (
                float(rows.iloc[0]['discount'])
                if 'discount' in df.columns and not pd.isna(rows.iloc[0]['discount'])
                else 0
            )

            purchase.net_total = net_total
            purchase.discount_amount = discount
            purchase.grand_total = net_total - discount
            purchase.remaining_amount = purchase.grand_total

            purchase.save(update_fields=[
                'net_total',
                'discount_amount',
                'grand_total',
                'remaining_amount'
            ])

            created.append(purchase.id)

        except Exception as e:
            errors.append({
                "purchase_ref": ref,
                "error": str(e)
            })

    return {
        "created_purchases": created,
        "errors": errors
    }
