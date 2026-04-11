import pandas as pd
from django.db import transaction
from core.models import Stock, Category
import logging

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['item_no', 'name', 'category', 'model', 'purchase_price', 'stock']


def upload_stock_excel(file):
    try:
        df = pd.read_excel(file)
    except Exception as e:
        return {"error": f"File read failed: {e}"}

    # ── Validate required columns ──────────────────────────────────────────
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return {"error": f"Missing columns: {', '.join(missing)}"}

    # ── Optional columns ───────────────────────────────────────────────────
    if 'is_migrated' not in df.columns:
        df['is_migrated'] = False
    if 'block' not in df.columns:
        df['block'] = ''

    # ── Clean & normalize ──────────────────────────────────────────────────
    df['item_no']        = df['item_no'].astype(str).str.strip()
    df['name']           = df['name'].astype(str).str.strip()
    df['category']       = df['category'].fillna('Uncategorized').astype(str).str.strip()
    df['model']          = df['model'].fillna('').astype(str).str.strip()
    df['block']          = df['block'].fillna('').astype(str).str.strip()
    df['is_migrated']    = df['is_migrated'].astype(str).str.strip().str.upper() == 'TRUE'
    df['stock']          = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int).clip(lower=0)
    df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce').fillna(0.0)
    df['purchase_price'] = df['purchase_price'].apply(lambda x: 0.0 if x < 0 else x)
    df['sale_price']     = df['purchase_price'].apply(lambda x: round(x * 1.13, 2) if x > 0 else 0.0)

    # ── Remove empty item_no rows ──────────────────────────────────────────
    df = df[df['item_no'].str.len() > 0].reset_index(drop=True)

    errors = []

    # ── Duplicate item_no within Excel itself ──────────────────────────────
    excel_dup_mask = df.duplicated(subset='item_no', keep='first')
    for _, row in df[excel_dup_mask].iterrows():
        errors.append({
            "item_no": row['item_no'],
            "name": row['name'],
            "error": "Duplicate item_no in Excel — only first occurrence used"
        })
    df = df[~excel_dup_mask].reset_index(drop=True)

    to_create = []  # define early so finally/return block can reference it

    try:
        with transaction.atomic():

            # ── Bulk create categories ─────────────────────────────────────
            category_names = df['category'].unique().tolist()
            existing_cats = {c.name: c for c in Category.objects.filter(name__in=category_names)}
            new_cats = [Category(name=n) for n in category_names if n not in existing_cats]
            if new_cats:
                Category.objects.bulk_create(new_cats, ignore_conflicts=True)
            all_cats = {c.name: c for c in Category.objects.filter(name__in=category_names)}

            # ── Skip item_nos already in DB ────────────────────────────────
            existing_item_nos = set(
                Stock.objects.filter(item_no__in=df['item_no'])
                .values_list('item_no', flat=True)
            )
            for _, row in df[df['item_no'].isin(existing_item_nos)].iterrows():
                errors.append({
                    "item_no": row['item_no'],
                    "name": row['name'],
                    "error": "Already exists in DB (item_no) — edit manually"
                })
            df = df[~df['item_no'].isin(existing_item_nos)].reset_index(drop=True)

            # ── Skip name+model+category combos already in DB ──────────────
            # This prevents the UNIQUE constraint crash on core_stock(name, model, category_id)
            existing_combos = set(
                Stock.objects.filter(name__in=df['name'].tolist())
                .values_list('name', 'model', 'category__name')
            )

            name_model_cat_dup_mask = df.apply(
                lambda row: (row['name'], row['model'], row['category']) in existing_combos,
                axis=1
            )
            for _, row in df[name_model_cat_dup_mask].iterrows():
                errors.append({
                    "item_no": row['item_no'],
                    "name": row['name'],
                    "error": "Duplicate name+model+category already in DB — edit manually"
                })
            df = df[~name_model_cat_dup_mask].reset_index(drop=True)

            # ── Bulk insert remaining rows ─────────────────────────────────
            to_create = [
                Stock(
                    item_no=row.item_no,
                    name=row.name,
                    category=all_cats.get(row.category),
                    model=row.model,
                    purchase_price=float(row.purchase_price),
                    sale_price=float(row.sale_price),
                    stock=int(row.stock),
                    is_migrated=bool(row.is_migrated),
                    block=row.block,
                )
                for row in df.itertuples(index=False)
            ]

            if to_create:
                Stock.objects.bulk_create(to_create, batch_size=1000)

    except Exception as e:
        logger.exception("Stock upload failed")
        return {"error": str(e)}

    return {
        "success": True,
        "summary": {
            "total_rows": len(df) + len(errors),
            "created": len(to_create),
            "skipped_db_duplicates": len([e for e in errors if "Already exists" in e["error"]]),
            "skipped_name_model_cat_duplicates": len([e for e in errors if "name+model+category" in e["error"]]),
            "skipped_excel_duplicates": len([e for e in errors if "Excel" in e["error"]]),
        },
        "errors": errors,
    }