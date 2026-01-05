import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Staff, Supplier, Stock


@transaction.atomic
def upload_purchase_excel(file, user):
    """
    Uploads purchases from Excel file.

    Expected columns:
    - purchase_ref
    - supplier
    - date
    - item_no
    - quantity
    - price
    Optional:
    - vat
    - sale_price
    """
    df = pd.read_excel(file)

    # Required columns check
    required_cols = ['purchase_ref', 'supplier', 'date', 'item_no', 'quantity', 'price']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Optional columns
    optional_cols = ['vat', 'sale_price']

    grouped = df.groupby("purchase_ref")
    created = []
    errors = []

    for ref, rows in grouped:
        try:
            # Supplier lookup
            supplier_name = rows.iloc[0]['supplier']
            try:
                supplier = Supplier.objects.get(name=supplier_name)
            except Supplier.DoesNotExist:
                raise ValueError(f"Supplier '{supplier_name}' does not exist.")
            
            # Map user → staff
            staff = getattr(user, 'staff', None)
            if not staff:
                # fallback: get or create a dummy staff
                staff, _ = Staff.objects.get_or_create(
                    name=f"Imported by {user.username}",
                    email=user.email
                )


            # Create Purchase
            purchase = Purchase.objects.create(
                supplier=supplier,
                date=rows.iloc[0]['date'],
                created_by=staff,
                is_migrated=True  # mark as imported
            )

            purchase_items = []
            total_net = 0
            total_vat = 0

            for idx, row in rows.iterrows():
                try:
                    item = Stock.objects.get(item_no=row['item_no'])
                except Stock.DoesNotExist:
                    raise ValueError(f"Row {idx + 2}: Item with item_no '{row['item_no']}' does not exist.")

                quantity = int(row['quantity'])
                price = float(row['price'])
                sale_price = float(row['sale_price']) if 'sale_price' in row and not pd.isna(row['sale_price']) else price

                total_item_price = price * quantity
                total_net += total_item_price

                purchase_items.append(
                    PurchaseItem(
                        purchase=purchase,
                        item=item,
                        quantity=quantity,
                        price=price,
                        sale_price=sale_price
                    )
                )

            # Bulk create PurchaseItems
            PurchaseItem.objects.bulk_create(purchase_items)

            # Update Purchase totals
            purchase.net_total = total_net
            purchase.vat_amount = total_vat
            purchase.grand_total = total_net + total_vat
            purchase.remaining_amount = purchase.grand_total - purchase.paid_amount
            purchase.save(update_fields=['net_total', 'vat_amount', 'grand_total', 'remaining_amount'])

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
