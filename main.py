"""DeskFlow demo: runs the full stage-1 scenario from data file to report.

Run from the repository root:  python main.py
"""

from __future__ import annotations

from datetime import datetime
from itertools import islice
from pathlib import Path

from deskflow.context_managers import TicketWorkSession
from deskflow.iterators import TicketBoard, iter_overdue, traced, urgent_unassigned_pipeline
from deskflow.models import Helpdesk, NetworkTicket, Technician, Ticket
from deskflow.processing import (
    DispatchQueues,
    active_buildings,
    count_by_category,
    departments,
    group_by_technician,
    open_tickets,
    reporter_overlap,
    sort_by_age,
    sort_by_deadline,
    sort_for_report,
    split_location,
    summary_row,
    title_index,
)
from deskflow.repository import load_employees, load_tickets

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_FILE = DATA_DIR / "sample_data.jsonl"
INVALID_FILE = DATA_DIR / "invalid_examples.jsonl"

# A fixed "current time" so the output is the same on every run.
NOW = datetime(2026, 10, 19, 16, 0)


def section(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def build_helpdesk(tickets: dict[int, Ticket]) -> Helpdesk:
    desk = Helpdesk("DeskFlow HQ")
    for tech in (
        Technician("T1", "Yossi Biton", {"hardware", "network"}),
        Technician("T2", "Maya Friedman", {"software"}),
        Technician("T3", "Avi Golan", {"hardware", "software", "network"}),
    ):
        desk.add_technician(tech)
    for ticket in tickets.values():
        desk.add_ticket(ticket)
        if ticket.status == "in_progress" and ticket.assigned_to:
            desk.assign(ticket.ticket_id, ticket.assigned_to)
    return desk


def demo_loading() -> tuple[dict[int, Ticket], dict]:
    section("1. Loading data")
    tickets, errors = load_tickets(SAMPLE_FILE)
    employees = load_employees(SAMPLE_FILE)
    print(f"Loaded {len(tickets)} tickets and {len(employees)} employees from {SAMPLE_FILE.name}")
    print(f"Errors in sample data: {len(errors)}")

    _, bad_errors = load_tickets(INVALID_FILE)
    print(f"\nValidation check with {INVALID_FILE.name}:")
    for message in bad_errors:
        print(f"  - {message}")
    return tickets, employees


def demo_oop(desk: Helpdesk) -> None:
    section("2. OOP: polymorphism, validation, composition")
    print(desk)
    for tech in desk.technicians:
        print(f"  {tech}")

    print("\nSame call, different behavior per ticket type (no if/elif on the type):")
    for ticket_id in (102, 103, 109, 104):
        t = desk.find(ticket_id)
        print(f"  {t}")
        print(f"      impact: {t.impact():<32} SLA {t.sla_hours():>5.1f}h  due {t.due_at:%d/%m %H:%M}")

    print(f"\nrepr: {desk.find(104)!r}")

    print("\nInvalid values raise ValueError:")
    attempts = [
        ("priority = 9", lambda: setattr(desk.find(102), "priority", 9)),
        ("empty title", lambda: setattr(desk.find(102), "title", "  ")),
        ("reopen closed ticket", lambda: setattr(desk.find(108), "status", "open")),
        ("affected_users = 0", lambda: setattr(desk.find(104), "affected_users", 0)),
        ("duplicate ticket id", lambda: desk.add_ticket(desk.find(101))),
        ("software ticket to T1", lambda: desk.assign(113, "T1")),
    ]
    for label, action in attempts:
        try:
            action()
        except ValueError as exc:
            print(f"  {label:<24} -> {exc}")


def demo_data_structures(desk: Helpdesk, employees: dict) -> None:
    section("3. Data structures")
    tickets = desk.tickets

    print("Tickets per category (dict for counting):")
    for category, count in count_by_category(tickets).items():
        print(f"  {category:<10} {count}")

    print("\nOpen tickets per technician (dict for grouping):")
    for tech_id, group in group_by_technician(tickets).items():
        ids = ", ".join(f"#{t.ticket_id}" for t in group)
        print(f"  {tech_id:<11} {ids}")

    print("\nLookup by id with .get():", desk.find(999) or "ticket #999 not found")

    building, details = split_location(desk.find(112).location)
    print(f"\nUnpacking location with *: building={building!r}, details={details}")
    print("Summary row (tuple):", summary_row(desk.find(112)))

    buildings = active_buildings(tickets)
    print(f"\nBuildings with open tickets (set): {sorted(buildings)}")
    print(f"  'Branch North' in set? {'Branch North' in buildings}")
    overlap = reporter_overlap(tickets)
    print(f"  urgent AND network reporters: {sorted(overlap['both'])}")
    print(f"  urgent OR network reporters:  {len(overlap['either'])} people")
    print(f"  urgent but NOT network:       {sorted(overlap['urgent_not_network'])}")

    print(f"\nDepartments (set comprehension): {sorted(departments(employees.values()))}")


def demo_dispatch(desk: Helpdesk) -> None:
    section("4. Dispatch queues: deque (FIFO) + heapq (priority)")
    queues = DispatchQueues()
    waiting = [t for t in desk.tickets if t.status == "open"]
    for ticket in sort_by_age(waiting):  # add in arrival order
        queues.add(ticket)
    urgent, regular = queues.sizes
    print(f"Queued: {urgent} urgent, {regular} regular")

    print("\nOrder in which free technicians get tickets:")
    position = 1
    while (ticket := queues.next_ticket()) is not None:
        print(f"  {position:>2}. {ticket}  created {ticket.created_at:%d/%m %H:%M}")
        position += 1
    print(f"Queue empty -> next_ticket() returns {queues.next_ticket()} (no crash)")


def demo_sorting_and_comprehensions(desk: Helpdesk) -> None:
    section("5. Sorting and comprehensions")
    still_open = open_tickets(desk.tickets)
    print(f"Open tickets (list comprehension): {len(still_open)}")

    print("\nThree oldest open tickets (key=regular function):")
    for t in sort_by_age(still_open)[:3]:
        print(f"  #{t.ticket_id} created {t.created_at:%d/%m %H:%M}")

    print("\nThree nearest deadlines (key=lambda):")
    for t in sort_by_deadline(still_open)[:3]:
        print(f"  #{t.ticket_id} due {t.due_at:%d/%m %H:%M}")

    print("\nReport order: category, then priority (key=tuple of two fields):")
    for t in sort_for_report(still_open):
        print(f"  {t.category:<9} p{t.priority}  #{t.ticket_id} {t.title}")

    index = title_index(desk.tickets)
    print(f"\nTitle index (dict comprehension), #118 -> {index[118]!r}")


def demo_iterators(desk: Helpdesk) -> None:
    section("6. Custom Iterable / Iterator")
    board = TicketBoard(desk.find(i) for i in (104, 112, 118, 101))
    first = iter(board)
    second = iter(board)
    print(f"Two iterators on the same board: {first is not second}")
    print(f"  first  -> #{next(first).ticket_id}, #{next(first).ticket_id}")
    print(f"  second -> #{next(second).ticket_id}   (starts again, independent)")
    print(f"  first  -> #{next(first).ticket_id}   (continues from its own position)")
    print("  for loop over the board:", [t.ticket_id for t in board])
    try:
        for _ in range(10):
            next(second)
    except StopIteration:
        print("  second iterator finished -> StopIteration")


def demo_generator(desk: Helpdesk) -> None:
    section("7. Generator with yield: overdue tickets")
    overdue = iter_overdue(sort_by_age(desk.tickets), NOW)
    print(f"Generator created, nothing processed yet: {overdue}")
    first = next(overdue)
    print(f"next() -> {first}")
    print("for loop continues from where the generator stopped:")
    for ticket in overdue:
        late = ticket.hours_open(NOW) - ticket.sla_hours()
        print(f"  {ticket}  ({late:.1f}h late)")
    print(f"Second loop over the same generator: {list(overdue)} -> exhausted")
    again = iter_overdue(desk.tickets, NOW)
    print(f"A new generator is needed to start over: {sum(1 for _ in again)} overdue tickets")


def demo_pipeline(desk: Helpdesk) -> None:
    section("8. Lazy pipeline (generator expressions)")
    source = sort_by_age(desk.tickets)
    seen: list[int] = []
    pipeline = urgent_unassigned_pipeline(traced(source, seen))
    print(f"Pipeline built, tickets read so far: {seen}")
    first_two = list(islice(pipeline, 2))
    print(f"First two urgent unassigned tickets: {first_two}")
    print(f"Tickets read from the source: {len(seen)} of {len(source)} -> {seen}")
    skipped = [t.ticket_id for t in source if t.ticket_id not in seen]
    print(f"Never processed (not needed after stopping): {skipped}")


def demo_context_manager(desk: Helpdesk) -> None:
    section("9. Context manager: technician work session")
    ticket = desk.find(102)
    desk.assign(102, "T1")
    print(f"Before: {ticket}, locked_by={ticket.locked_by}")
    with TicketWorkSession(ticket, "T1") as session:
        print(f"Inside: status={ticket.status}, locked_by={ticket.locked_by}")
        desk.close_ticket(102, "Replaced the power adapter", NOW)
    print(f"After:  {ticket}, locked_by={ticket.locked_by}, failed={session.failed}")

    print("\nFailure inside the block:")
    ticket = desk.find(104)
    desk.assign(104, "T3")
    session = TicketWorkSession(ticket, "T3")
    try:
        with session:
            print(f"Inside: status={ticket.status}, locked_by={ticket.locked_by}")
            raise ConnectionError("cannot reach the floor 4 switch")
    except ConnectionError as exc:
        print(f"Exception reached the caller: {exc}")
    print(f"After:  status restored to {ticket.status!r}, locked_by={ticket.locked_by}")
    print(f"        note: {ticket.notes[-1]}")
    print(f"        failed={session.failed}, time recorded={session.duration_seconds >= 0}")

    print("\nA closed ticket cannot start a new session:")
    try:
        with TicketWorkSession(desk.find(102), "T1"):
            pass
    except ValueError as exc:
        print(f"  {exc}")


def demo_summary(desk: Helpdesk) -> None:
    section("10. End of day summary")
    for status, count in desk.count_by_status().items():
        print(f"  {status:<12} {count}")
    wide = [t for t in desk.tickets if isinstance(t, NetworkTicket) and t.affected_users >= 20]
    print(f"  wide network outages: {[t.ticket_id for t in wide]}")


def main() -> None:
    tickets, employees = demo_loading()
    desk = build_helpdesk(tickets)
    demo_oop(desk)
    demo_data_structures(desk, employees)
    demo_dispatch(desk)
    demo_sorting_and_comprehensions(desk)
    demo_iterators(desk)
    demo_generator(desk)
    demo_pipeline(desk)
    demo_context_manager(desk)
    demo_summary(desk)


if __name__ == "__main__":
    main()
