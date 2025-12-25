import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Supplier, Stock


@transaction.atomic
def upload_purchase_excel(file, user):
    # Read Excel file
    df = pd.read_excel(file)

    # Required columns
    required = ['purchase_ref', 'supplier', 'date', 'item_no', 'quantity', 'price']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # Optional columns
    optional = ['vat', 'sale_price']

    # Group by purchase reference
    grouped = df.groupby("purchase_ref")

    created = []
    errors = []

    for ref, rows in grouped:
        try:
            # Get supplier
            supplier_name = rows.iloc[0]['supplier']
            try:
                supplier = Supplier.objects.get(name=supplier_name)
            except Supplier.DoesNotExist:
                raise ValueError(f"Supplier '{supplier_name}' does not exist.")

            # Create Purchase
            purchase = Purchase.objects.create(
                supplier=supplier,
                date=rows.iloc[0]['date'],
                created_by=user,
                is_migrated=True  # mark as imported
            )

            # Create PurchaseItems
            for _, row in rows.iterrows():
                try:
                    item = Stock.objects.get(item_no=row['item_no'])
                except Stock.DoesNotExist:
                    raise ValueError(f"Item with item_no '{row['item_no']}' does not exist.")

                # Handle VAT and Sale Price
                vat = float(row['vat']) if 'vat' in row and not pd.isna(row['vat']) else 0.0
                sale_price = float(row['sale_price']) if 'sale_price' in row and not pd.isna(row['sale_price']) else float(row['price'])

                PurchaseItem.objects.create(
                    purchase=purchase,
                    item=item,
                    quantity=int(row['quantity']),
                    price=float(row['price']),
                    vat=vat,
                    sale_price=sale_price
                )

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
