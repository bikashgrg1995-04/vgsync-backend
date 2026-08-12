# core/management/commands/restore_data.py
#
# USAGE:
#   python manage.py restore_data backups/2025-05-28/data.json
#   python manage.py restore_data D:\vgsync\vgsync-backend\backups\2025-05-28\data.json

import os
from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from django.db import transaction
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete

from core.models import (
    PurchaseItem, Purchase,
    SaleItem, Sale,
    SalaryTransaction,
    BikeSale,
    OrderItem,
)
import core.signals as sig


SIGNAL_REGISTRY = [
    (pre_save,    PurchaseItem,       sig.store_old_purchase_qty),
    (post_save,   PurchaseItem,       sig.adjust_stock_on_purchase_save),
    (pre_delete,  PurchaseItem,       sig.restore_stock_on_purchase_delete),
    (post_save,   Purchase,           sig.sync_purchase_expense),
    (pre_delete,  Purchase,           sig.delete_purchase_expense),
    (pre_save,    SaleItem,           sig.store_old_sale_qty),
    (post_save,   SaleItem,           sig.adjust_stock_on_sale_save),
    (pre_delete,  SaleItem,           sig.restore_stock_on_sale_delete),
    (post_save,   Sale,               sig.manage_followup_dashboard),
    (pre_delete,  Sale,               sig.delete_followup_on_sale_delete),
    (post_save,   OrderItem,          sig.update_order_totals),
    (post_delete, OrderItem,          sig.update_order_totals),
    (post_save,   SalaryTransaction,  sig.handle_salary_transaction_save),
    (pre_delete,  SalaryTransaction,  sig.handle_salary_transaction_delete),
    (post_save,   BikeSale,           sig.bike_sale_followup),
    (pre_delete,  BikeSale,           sig.delete_bike_sale_followup),
]


class Command(BaseCommand):
    help = "Restore a JSON fixture without firing Django signals."

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture",
            type=str,
            help="Path to the JSON fixture file",
        )

    def handle(self, *args, **options):
        fixture_path = os.path.abspath(options["fixture"])

        # ── 0. Validate file ──────────────────────────────────────────────────
        if not os.path.isfile(fixture_path):
            raise CommandError(
                f"File not found: {fixture_path}\n"
                f"Full path dinu parcha, e.g.:\n"
                f"  python manage.py restore_data D:\\vgsync\\backups\\2025-05-28\\data.json"
            )

        self.stdout.write(self.style.WARNING(
            f"\n⚡  Disconnecting {len(SIGNAL_REGISTRY)} signal receivers..."
        ))

        # ── 1. Disconnect all signals ─────────────────────────────────────────
        for signal, sender, receiver_fn in SIGNAL_REGISTRY:
            signal.disconnect(receiver_fn, sender=sender)

        # ── 2. Load directly using Django's deserializer (bypasses loaddata path logic)
        self.stdout.write(self.style.WARNING(
            f"\n📥  Loading: {fixture_path}..."
        ))
        try:
            with open(fixture_path, encoding="utf-8") as f:
                data = f.read()

            objects = list(serializers.deserialize("json", data))
            count = 0

            with transaction.atomic():
                for obj in objects:
                    obj.save()
                    count += 1

            self.stdout.write(self.style.SUCCESS(
                f"\n✅  {count} records loaded successfully!"
            ))

        except Exception as exc:
            self._reconnect_signals()
            raise CommandError(f"Restore failed: {exc}") from exc

        # ── 3. Reconnect signals ──────────────────────────────────────────────
        self._reconnect_signals()
        self.stdout.write(self.style.SUCCESS(
            f"🔁  All {len(SIGNAL_REGISTRY)} signal receivers reconnected.\n"
        ))

    def _reconnect_signals(self):
        for signal, sender, receiver_fn in SIGNAL_REGISTRY:
            signal.connect(receiver_fn, sender=sender)
        self.stdout.write(self.style.WARNING("   ✓  Signals reconnected."))