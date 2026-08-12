import pandas as pd
from django.db import transaction
from core.models import Stock, Category
import logging

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['item_no', 'purchase_price']


def upload_mrp_excel(file):
    try:
        df = pd.read_excel(file)
    except Exception as e:
        return {"error": f"File read failed: {e}"}

    # ── Validate required columns ──────────────────────────────────────────
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return {"error": f"Missing columns: {', '.join(missing)}"}

    # ── Clean & normalize ──────────────────────────────────────────────────
    df['item_no']        = df['item_no'].astype(str).str.strip()
    df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce').fillna(0.0)
    df['purchase_price'] = df['purchase_price'].apply(lambda x: 0.0 if x < 0 else x)
    df['sale_price']     = df['purchase_price'].apply(lambda x: round(x * 1.13, 2) if x > 0 else 0.0)

    # ── Optional columns ───────────────────────────────────────────────────
    has_name     = 'name'     in df.columns
    has_category = 'category' in df.columns
    has_model    = 'model'    in df.columns

    if has_name:     df['name']     = df['name'].astype(str).str.strip()
    if has_category: df['category'] = df['category'].astype(str).str.strip()
    if has_model:    df['model']    = df['model'].astype(str).str.strip()

    # ── Remove empty item_no rows ──────────────────────────────────────────
    df = df[df['item_no'].str.len() > 0].reset_index(drop=True)

    total_rows = len(df)
    errors  = []
    updated = []
    created = []

    # ── Duplicate item_no within Excel itself ──────────────────────────────
    excel_dup_mask = df.duplicated(subset='item_no', keep='first')
    for _, row in df[excel_dup_mask].iterrows():
        errors.append({
            "item_no": row['item_no'],
            "error": "Duplicate item_no in Excel — only first occurrence used"
        })
    df = df[~excel_dup_mask].reset_index(drop=True)

    try:
        with transaction.atomic():

            # ── Default category & model for new stocks ────────────────────
            default_category, _ = Category.objects.get_or_create(name="N/A")

            # ── Category map (if category column present) ──────────────────
            category_map = {
                c.name.lower(): c
                for c in Category.objects.all()
            }

            # ── Fetch existing stocks ──────────────────────────────────────
            existing_stocks = {
                s.item_no: s
                for s in Stock.objects.filter(item_no__in=df['item_no'].tolist())
            }

            # ── Split: found vs not found ──────────────────────────────────
            not_found_mask = ~df['item_no'].isin(existing_stocks)
            df_not_found   = df[not_found_mask].reset_index(drop=True)
            df_found       = df[~not_found_mask].reset_index(drop=True)

            # ── Create new stocks ──────────────────────────────────────────
            to_create = []
            for _, row in df_not_found.iterrows():

                # category resolve गर्ने
                if has_category and str(row['category']).strip():
                    category_obj = category_map.get(row['category'].lower())
                    if not category_obj:
                        # DB मा category नभेटे — नयाँ create गर्ने
                        category_obj, _ = Category.objects.get_or_create(name=row['category'].strip())
                        category_map[row['category'].lower()] = category_obj
                else:
                    category_obj = default_category  # "Uncategorized"

                to_create.append(Stock(
                    item_no        = row['item_no'],
                    name           = row['name']     if has_name     else row['item_no'],
                    model          = row['model']    if has_model    else 'N/A',
                    category       = category_obj,
                    purchase_price = float(row['purchase_price']),
                    sale_price     = float(row['sale_price']),
                    is_migrated    = True,
                ))
                created.append({
                    "item_no":            row['item_no'],
                    "new_purchase_price": float(row['purchase_price']),
                    "new_sale_price":     float(row['sale_price']),
                })

            if to_create:
                Stock.objects.bulk_create(to_create, batch_size=1000)

            # ── Update existing stocks ─────────────────────────────────────
            to_update = []
            for row in df_found.itertuples(index=False):
                stock_obj = existing_stocks[row.item_no]
                stock_obj.purchase_price = float(row.purchase_price)
                stock_obj.sale_price     = float(row.sale_price)
                to_update.append(stock_obj)
                updated.append({
                    "item_no":            row.item_no,
                    "new_purchase_price": float(row.purchase_price),
                    "new_sale_price":     float(row.sale_price),
                })

            if to_update:
                Stock.objects.bulk_update(
                    to_update,
                    fields=['purchase_price', 'sale_price'],
                    batch_size=1000,
                )

    except Exception as e:
        logger.exception("MRP upload failed")
        return {"error": str(e)}

    return {
        "success": True,
        "summary": {
            "total_rows":         total_rows,
            "updated":            len(updated),
            "created":            len(created),
            "skipped_excel_dups": len([e for e in errors if "Excel" in e["error"]]),
        },
        "errors":  errors,
        "updated": updated,
        "created": created,
    }