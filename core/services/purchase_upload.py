import pandas as pd
from django.db import transaction
from core.models import Purchase, PurchaseItem, Supplier, Stock


@transaction.atomic
def upload_purchase_excel(file, user):
    df = pd.read_excel(file)

    required = ['purchase_ref', 'supplier', 'date', 'item_no', 'quantity', 'price']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    grouped = df.groupby("purchase_ref")

    created = []
    errors = []

    for ref, rows in grouped:
        try:
            supplier = Supplier.objects.get(name=rows.iloc[0]['supplier'])

            purchase = Purchase.objects.create(
                supplier=supplier,
                date=rows.iloc[0]['date'],
                created_by=user,
                is_migrated=True  # 🔴 PURE DATA
            )

            for _, row in rows.iterrows():
                item = Stock.objects.get(item_no=row['item_no'])

                PurchaseItem.objects.create(
                    purchase=purchase,
                    item=item,
                    quantity=int(row['quantity']),
                    price=float(row['price'])
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
