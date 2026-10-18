"""Reading the JSONL data file and converting it into model objects."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .models import Employee, Ticket

REQUIRED_FIELDS = (
    "id",
    "category",
    "title",
    "reporter_name",
    "reporter_email",
    "department",
    "priority",
    "created_at",
    "location",
)


def iter_records(path: str | Path) -> Iterator[tuple[int, dict | None, str | None]]:
    """Read the file line by line (never all at once).

    Yields (line_number, record, error). Exactly one of record / error is set.
    """
    with open(path, encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_no, None, f"line {line_no}: invalid JSON ({exc.msg})"
                continue
            if not isinstance(record, dict):
                yield line_no, None, f"line {line_no}: expected a JSON object"
                continue
            missing = [field for field in REQUIRED_FIELDS if field not in record]
            if missing:
                yield line_no, None, f"line {line_no}: missing fields {missing}"
                continue
            yield line_no, record, None


def load_tickets(path: str | Path) -> tuple[dict[int, Ticket], list[str]]:
    """Return a dict {ticket_id: Ticket} and a list of error messages.

    Duplicate ids: the first record is kept and the duplicate is reported.
    """
    tickets: dict[int, Ticket] = {}
    errors: list[str] = []
    for line_no, record, error in iter_records(path):
        if error:
            errors.append(error)
            continue
        try:
            ticket = Ticket.from_dict(record)
        except ValueError as exc:
            errors.append(f"line {line_no}: {exc}")
            continue
        if ticket.ticket_id in tickets:
            errors.append(f"line {line_no}: duplicate id {ticket.ticket_id}, kept the first record")
            continue
        tickets[ticket.ticket_id] = ticket
    return tickets, errors


def load_employees(path: str | Path) -> dict[str, Employee]:
    """Return {email: Employee} for every reporter in the file (first record wins)."""
    employees: dict[str, Employee] = {}
    for _, record, error in iter_records(path):
        if error:
            continue
        try:
            employee = Employee.from_ticket_record(record)
        except ValueError:
            continue
        employees.setdefault(employee.email, employee)
    return employees
