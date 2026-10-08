#!/usr/bin/env python3
"""Учебная система учёта компьютерной техники, Python 3.10+."""
from __future__ import annotations
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VALID_KINDS = {"desktop", "laptop", "monitor", "printer", "server", "other"}
VALID_STATUSES = {"in_stock", "in_use", "retired"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InventoryError(Exception):
    pass


class EquipmentRepository:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def close(self):
        self.conn.close()

    def init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY,
                inventory_tag TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                model TEXT NOT NULL,
                serial TEXT UNIQUE,
                location TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('in_stock', 'in_use', 'retired')),
                assigned_to TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                equipment_id INTEGER NOT NULL REFERENCES equipment(id),
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def _event(self, equipment_id: int, action: str, details: str):
        self.conn.execute(
            "INSERT INTO events(equipment_id, action, details, created_at) VALUES(?,?,?,?)",
            (equipment_id, action, details, utc_now()),
        )

    def add(self, tag: str, kind: str, model: str, serial: str | None, location: str):
        tag, model, location = tag.strip(), model.strip(), location.strip()
        serial = (serial or "").strip() or None
        if not all((tag, model, location)):
            raise InventoryError("Инвентарный номер, модель и кабинет обязательны")
        if kind not in VALID_KINDS:
            raise InventoryError("Недопустимый тип оборудования")
        now = utc_now()
        try:
            with self.conn:
                cur = self.conn.execute(
                    """INSERT INTO equipment(inventory_tag,kind,model,serial,location,status,
                       assigned_to,created_at,updated_at) VALUES(?,?,?,?,?,'in_stock',NULL,?,?)""",
                    (tag, kind, model, serial, location, now, now),
                )
                self._event(cur.lastrowid, "created", "Карточка оборудования создана")
        except sqlite3.IntegrityError as exc:
            raise InventoryError("Инвентарный или серийный номер уже зарегистрирован") from exc
        return self.get(tag)

    def get(self, tag: str):
        row = self.conn.execute(
            "SELECT * FROM equipment WHERE inventory_tag = ?", (tag,)
        ).fetchone()
        if row is None:
            raise InventoryError(f"Оборудование {tag!r} не найдено")
        return dict(row)

    def list(self, status: str | None = None):
        if status and status not in VALID_STATUSES:
            raise InventoryError("Недопустимый статус")
        if status:
            rows = self.conn.execute(
                "SELECT * FROM equipment WHERE status=? ORDER BY inventory_tag", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM equipment ORDER BY inventory_tag").fetchall()
        return [dict(x) for x in rows]

    def assign(self, tag: str, person: str, location: str):
        person, location = person.strip(), location.strip()
        if not person or not location:
            raise InventoryError("Необходимо указать сотрудника и кабинет")
        with self.conn:
            item = self.get(tag)
            if item["status"] == "retired":
                raise InventoryError("Нельзя выдать списанное оборудование")
            self.conn.execute(
                "UPDATE equipment SET status='in_use',assigned_to=?,location=?,updated_at=? WHERE id=?",
                (person, location, utc_now(), item["id"]),
            )
            self._event(item["id"], "assigned", f"Выдано: {person}; расположение: {location}")
        return self.get(tag)

    def retire(self, tag: str, reason: str):
        reason = reason.strip()
        if not reason:
            raise InventoryError("Укажите основание списания")
        with self.conn:
            item = self.get(tag)
            if item["status"] == "retired":
                raise InventoryError("Оборудование уже списано")
            self.conn.execute(
                "UPDATE equipment SET status='retired',assigned_to=NULL,updated_at=? WHERE id=?",
                (utc_now(), item["id"]),
            )
            self._event(item["id"], "retired", f"Списано: {reason}")
        return self.get(tag)

    def stats(self):
        result = {key: 0 for key in ["in_stock", "in_use", "retired"]}
        for row in self.conn.execute("SELECT status, COUNT(*) AS n FROM equipment GROUP BY status"):
            result[row["status"]] = row["n"]
        result["total"] = sum(result.values())
        return result

    def history(self, tag: str):
        item = self.get(tag)
        rows = self.conn.execute(
            "SELECT action, details, created_at FROM events WHERE equipment_id=? ORDER BY id",
            (item["id"],),
        ).fetchall()
        return [dict(x) for x in rows]


def make_parser():
    parser = argparse.ArgumentParser(description="Учёт компьютерной техники")
    parser.add_argument("--db", default="inventory.sqlite3", help="Путь к SQLite БД")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("init")
    add = actions.add_parser("add")
    for flag in ("tag", "kind", "model", "location"):
        add.add_argument("--" + flag, required=True)
    add.add_argument("--serial")
    ls = actions.add_parser("list")
    ls.add_argument("--status", choices=sorted(VALID_STATUSES))
    show = actions.add_parser("show")
    show.add_argument("tag")
    assign = actions.add_parser("assign")
    assign.add_argument("tag")
    assign.add_argument("--person", required=True)
    assign.add_argument("--location", required=True)
    retire = actions.add_parser("retire")
    retire.add_argument("tag")
    retire.add_argument("--reason", required=True)
    actions.add_parser("stats")
    hist = actions.add_parser("history")
    hist.add_argument("tag")
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    try:
        repo = EquipmentRepository(args.db)
        try:
            if args.action == "init":
                value = {"result": "initialized", "database": args.db}
            elif args.action == "add":
                value = repo.add(args.tag,args.kind,args.model,args.serial,args.location)
            elif args.action == "list":
                value = repo.list(args.status)
            elif args.action == "show":
                value = repo.get(args.tag)
            elif args.action == "assign":
                value = repo.assign(args.tag,args.person,args.location)
            elif args.action == "retire":
                value = repo.retire(args.tag,args.reason)
            elif args.action == "stats":
                value = repo.stats()
            else:
                value = repo.history(args.tag)
            print(json.dumps(value, indent=2, ensure_ascii=False))
            return 0
        finally:
            repo.close()
    except (InventoryError, sqlite3.Error, OSError) as exc:
        print(f"Ошибка: {exc}", file=__import__('sys').stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
