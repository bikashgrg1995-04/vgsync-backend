import pandas as pd
from django.db import transaction
from core.models import Stock
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

    # ── Remove empty item_no rows ──────────────────────────────────────────
    df = df[df['item_no'].str.len() > 0].reset_index(drop=True)

    errors  = []
    updated = []

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

            # ── Fetch only stocks that exist ───────────────────────────────
            existing_stocks = {
                s.item_no: s
                for s in Stock.objects.filter(item_no__in=df['item_no'].tolist())
            }

            # ── Flag item_nos not found in DB ──────────────────────────────
            not_found_mask = ~df['item_no'].isin(existing_stocks)
            for _, row in df[not_found_mask].iterrows():
                errors.append({
                    "item_no": row['item_no'],
                    "error": "item_no not found in DB — skipped"
                })
            df = df[~not_found_mask].reset_index(drop=True)

            # ── Apply new prices ───────────────────────────────────────────
            to_update = []
            for row in df.itertuples(index=False):
                stock_obj = existing_stocks[row.item_no]
                stock_obj.purchase_price = float(row.purchase_price)
                stock_obj.sale_price     = float(row.sale_price)
                to_update.append(stock_obj)
                updated.append({
                    "item_no": row.item_no,
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
            "total_rows":          len(df) + len(errors),
            "updated":             len(updated),
            "skipped_not_found":   len([e for e in errors if "not found" in e["error"]]),
            "skipped_excel_dups":  len([e for e in errors if "Excel" in e["error"]]),
        },
        "errors":  errors,
        "updated": updated,
    }