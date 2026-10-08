import os
import tempfile
import unittest
from equipment import EquipmentRepository, InventoryError, main


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, "inventory.sqlite3")
        self.repo = EquipmentRepository(self.db)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def sample(self, tag="PC-001", serial="SN-1"):
        return self.repo.add(tag, "desktop", "ThinkCentre M70", serial, "Склад")

    def test_initial_database_empty(self):
        self.assertEqual(self.repo.stats()["total"], 0)

    def test_create_and_view_equipment(self):
        self.sample()
        self.assertEqual(self.repo.get("PC-001")["status"], "in_stock")
        self.assertEqual(len(self.repo.list()), 1)

    def test_duplicate_inventory_tag_forbidden(self):
        self.sample()
        with self.assertRaises(InventoryError):
            self.sample(serial="SN-2")

    def test_duplicate_serial_forbidden(self):
        self.sample()
        with self.assertRaises(InventoryError):
            self.sample(tag="PC-002")

    def test_assign_changes_person_and_location(self):
        self.sample()
        item = self.repo.assign("PC-001", "Петров И.И.", "Кабинет 3")
        self.assertEqual((item["status"], item["assigned_to"], item["location"]),
                         ("in_use", "Петров И.И.", "Кабинет 3"))

    def test_retire_prohibits_new_assignment(self):
        self.sample()
        self.repo.retire("PC-001", "Истёк срок эксплуатации")
        with self.assertRaises(InventoryError):
            self.repo.assign("PC-001", "Сидоров А.А.", "Кабинет 1")

    def test_second_retire_prohibited(self):
        self.sample()
        self.repo.retire("PC-001", "Износ")
        with self.assertRaises(InventoryError):
            self.repo.retire("PC-001", "Повтор")

    def test_stats_after_status_transitions(self):
        self.sample()
        self.repo.add("PC-002", "laptop", "Latitude", "SN-2", "Склад")
        self.repo.assign("PC-001", "Петров", "Кабинет 3")
        self.assertEqual(self.repo.stats(), {"in_stock": 1, "in_use": 1, "retired": 0, "total": 2})

    def test_audit_history(self):
        self.sample()
        self.repo.assign("PC-001", "Петров", "Кабинет 3")
        actions = [evt["action"] for evt in self.repo.history("PC-001")]
        self.assertEqual(actions, ["created", "assigned"])

    def test_nonexistent_equipment_error(self):
        with self.assertRaises(InventoryError):
            self.repo.get("UNKNOWN")

    def test_empty_field_error(self):
        with self.assertRaises(InventoryError):
            self.repo.add("", "desktop", "Model", None, "Warehouse")

    def test_cli_integration(self):
        self.assertEqual(main(["--db", self.db, "add", "--tag", "PC-1", "--kind", "monitor", "--model", "AOC", "--location", "Склад"]), 0)
        self.assertEqual(main(["--db", self.db, "stats"]), 0)
        self.assertEqual(self.repo.stats()["total"], 1)

if __name__ == "__main__":
    unittest.main()
