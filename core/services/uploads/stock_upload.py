import pandas as pd
from django.db import transaction
from core.models import Stock, Category

def upload_stock_excel(file):
    df = pd.read_excel(file)

    required_columns = [
        'item_no', 'name', 'category',
        'model', 'purchase_price', 'sale_price', 'stock'
    ]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        return {"error": f"Missing columns: {', '.join(missing)}"}

    created, updated, errors = [], [], []

    for idx, row in df.iterrows():
        try:
            with transaction.atomic():
                category, _ = Category.objects.get_or_create(
                    name=str(row['category']).strip()
                )

                stock, is_created = Stock.objects.update_or_create(
                    item_no=str(row['item_no']).strip(),
                    defaults={
                        "name": str(row['name']).strip(),
                        "category": category,
                        "model": str(row['model']).strip(),
                        "purchase_price": float(row['purchase_price']),
                        "sale_price": float(row['sale_price']),
                        "stock": int(row['stock']),
                    }
                )

                (created if is_created else updated).append(stock.item_no)

        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})

    return {
        "created": created,
        "updated": updated,
        "errors": errors
    }
