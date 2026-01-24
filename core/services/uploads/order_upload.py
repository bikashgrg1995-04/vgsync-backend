from collections import defaultdict
from django.db import transaction
import openpyxl

from core.models import Order, OrderItem, Stock
from core.services.utils import extract_item_no
from core.serializers import OrderExcelRowSerializer

def upload_order_excel(file):
    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    grouped_rows = defaultdict(list)
    row_errors = []

    for row_no, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        data = {
            "order_ref": row[0],
            "customer_name": row[1],
            "contact_no": row[2],
            "vehicle_model": row[3],
            "order_date": row[4],
            "advance": row[5] or 0,
            "item_no": row[6],
            "quantity": row[7],
            "rate": row[8],
        }

        serializer = OrderExcelRowSerializer(data=data)
        if serializer.is_valid():
            grouped_rows[serializer.validated_data["order_ref"]].append(
                serializer.validated_data
            )
        else:
            row_errors.append({"row": row_no, "errors": serializer.errors})

    created_orders, order_errors = [], []

    for order_ref, rows in grouped_rows.items():
        try:
            with transaction.atomic():
                first = rows[0]

                order = Order.objects.create(
                    customer_name=first["customer_name"].strip(),
                    contact_no=first["contact_no"].strip(),
                    vehicle_model=first["vehicle_model"].strip(),
                    order_date=first["order_date"],
                    advance=float(first["advance"]),
                )

                total = 0
                for r in rows:
                    stock = Stock.objects.get(
                        item_no=extract_item_no(r["item_no"]).upper()
                    )
                    qty, rate = int(r["quantity"]), float(r["rate"])
                    OrderItem.objects.create(
                        order=order, item=stock, quantity=qty, rate=rate
                    )
                    total += qty * rate

                order.total_amount = total
                order.remaining_amount = total - order.advance
                order.save()

                created_orders.append(order.id)

        except Exception as e:
            order_errors.append({
                "order_ref": order_ref,
                "error": str(e)
            })

    return {
        "created_orders": created_orders,
        "row_errors": row_errors,
        "order_errors": order_errors
    }
