"""
Tests for deterministic lock ordering during inventory reservation to prevent database deadlocks.
"""
import pytest
from unittest.mock import MagicMock
from app import create_app
from services.inventory_reservation_service import InventoryReservationService


@pytest.fixture
def test_app():
    app = create_app('testing')
    with app.app_context():
        yield app


def test_inventory_reservation_sorts_product_ids_preventing_deadlocks(test_app):
    """
    Two carts with the same products in opposite order must both acquire database
    row locks in ascending sorted order of product_id to eliminate circular wait deadlocks.
    """
    # Cart 1 has product IDs [20, 10] in descending order
    cart_reversed = {20: 1, 10: 2}
    # Cart 2 has product IDs [10, 20] in ascending order
    cart_ordered = {10: 2, 20: 1}

    executed_update_pids_cart1 = []
    executed_update_pids_cart2 = []

    class TrackingCursor:
        def __init__(self, record_list):
            self.record_list = record_list
            self.rowcount = 1

        def execute(self, sql, params=None):
            if "UPDATE products SET stock" in sql and params:
                # params is (required_qty, product_id, required_qty)
                self.record_list.append(params[1])

        def fetchone(self):
            return {'name': 'Mock Product', 'stock': 100}

    mock_conn = MagicMock()

    # Reserve cart 1 (reversed input)
    cur1 = TrackingCursor(executed_update_pids_cart1)
    InventoryReservationService.reserve_inventory(cur1, mock_conn, cart_reversed)

    # Reserve cart 2 (ordered input)
    cur2 = TrackingCursor(executed_update_pids_cart2)
    InventoryReservationService.reserve_inventory(cur2, mock_conn, cart_ordered)

    # Both must update in strictly ascending sorted order: [10, 20]
    assert executed_update_pids_cart1 == [10, 20], f"Cart 1 locked in wrong order: {executed_update_pids_cart1}"
    assert executed_update_pids_cart2 == [10, 20], f"Cart 2 locked in wrong order: {executed_update_pids_cart2}"
