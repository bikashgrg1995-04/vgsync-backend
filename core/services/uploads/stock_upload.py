import pandas as pd
from django.db import transaction
from core.models import Stock, Category

def upload_stock_excel(file):
    df = pd.read_excel(file)

    required_columns = [
        'item_no', 'name', 'category', 'model',
        'purchase_price', 'sale_price', 'stock',
        'is_migrated', 'block'
    ]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        return {"error": f"Missing columns: {', '.join(missing)}"}

    created, updated, errors = [], [], []

    for idx, row in df.iterrows():
        try:
            with transaction.atomic():
                # Ensure category exists
                category, _ = Category.objects.get_or_create(
                    name=str(row['category']).strip()
                )

                # Convert is_migrated to boolean safely
                is_migrated = str(row['is_migrated']).strip().upper() == 'TRUE'

                # Update or create Stock
                stock, is_created = Stock.objects.update_or_create(
                    item_no=str(row['item_no']).strip(),
                    defaults={
                        "name": str(row['name']).strip(),
                        "category": category,
                        "model": str(row['model']).strip(),
                        "purchase_price": float(row['purchase_price']),
                        "sale_price": float(row['sale_price']),
                        "stock": int(row['stock']),
                        "is_migrated": is_migrated,
                        "block": str(row['block']).strip(),
                    }
                )

                stock_data = {
                    "item_no": stock.item_no,
                    "name": stock.name,
                    "category": stock.category.name,
                    "model": stock.model,
                    "purchase_price": stock.purchase_price,
                    "sale_price": stock.sale_price,
                    "stock": stock.stock,
                    "is_migrated": stock.is_migrated,
                    "block": stock.block,
                }

                if is_created:
                    created.append(stock_data)
                else:
                    updated.append(stock_data)

        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})

    return {
        "created": created,
        "updated": updated,
        "errors": errors
    }
