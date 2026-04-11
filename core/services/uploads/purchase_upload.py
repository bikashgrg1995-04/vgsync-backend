import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Staff, Supplier, Stock


@transaction.atomic
def upload_purchase_excel(file, user):
    """
    Upload purchases from Excel.
    Expects columns:
    - purchase_ref
    - supplier
    - date
    - item_no
    - quantity
    - price
    - staff_id (optional)
    - discount (optional)
    """

    df = pd.read_excel(file)

    required_cols = ['purchase_ref', 'supplier', 'date', 'item_no', 'quantity', 'price', 'staff_id']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    grouped = df.groupby("purchase_ref")
    created, errors = [], []

    for ref, rows in grouped:
        try:
            # ---------------- Supplier ----------------
            supplier_name = rows.iloc[0]['supplier']
            supplier = Supplier.objects.get(name=supplier_name)

            # ---------------- Staff ----------------
            staff_id = rows.iloc[0]['staff_id']
            staff = None
            if not pd.isna(staff_id):
                try:
                    staff = Staff.objects.get(id=int(staff_id))
                except Staff.DoesNotExist:
                    staff = None  # Staff not found, leave as None

            # ---------------- Purchase ----------------
            purchase = Purchase.objects.create(
                supplier=supplier,
                date=rows.iloc[0]['date'],
                created_by=staff,
                is_migrated=True  # important to prevent automatic stock signals
            )

            items = []
            net_total = 0

            # ---------------- Items ----------------
            for _, row in rows.iterrows():
                item_no = row['item_no']
                try:
                    stock_item = Stock.objects.get(item_no=item_no)
                except Stock.DoesNotExist:
                    raise ValueError(f"Stock item not found: {item_no}")

                qty = int(row['quantity'])
                price = float(row['price'])

                net_total += qty * price

                items.append(
                    PurchaseItem(
                        purchase=purchase,
                        item=stock_item,
                        quantity=qty,
                        price=price
                    )
                )

            # Bulk create items
            PurchaseItem.objects.bulk_create(items)

            # ---------------- Discount ----------------
            discount = (
                float(rows.iloc[0]['discount'])
                if 'discount' in df.columns and not pd.isna(rows.iloc[0]['discount'])
                else 0
            )

            # ---------------- Totals ----------------

            purchase.grand_total = net_total          # items total
            purchase.discount_amount = discount        # discount amount
            purchase.net_total = net_total - discount  # discount काटेको
            purchase.remaining_amount = purchase.net_total - purchase.amount_paid  # initial remaining amount

            purchase.save(update_fields=['net_total', 'discount_amount', 'grand_total', 'remaining_amount'])

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
