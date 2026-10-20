"""Collections processing: queues, grouping, sets, comprehensions and sorting."""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Iterable

from .models import Employee, Ticket

# Priority 1 (critical) and 2 (high) go to the priority queue.
URGENT_PRIORITY_LIMIT = 2


class DispatchQueues:
    """Decides which ticket a free technician gets next.

    * Regular tickets (priority 3-4) wait in a FIFO deque: whoever reported
      first is served first. This keeps the process fair for routine requests.
    * Urgent tickets (priority 1-2) wait in a heapq priority queue. A smaller
      number means a higher priority. Ties are broken by Ticket.__lt__:
      earlier created_at first, then lower ticket id.
    * Urgent tickets are always served before regular ones.
    """

    def __init__(self) -> None:
        self._regular: deque[Ticket] = deque()
        self._urgent: list[Ticket] = []

    def add(self, ticket: Ticket) -> None:
        if ticket.status == "closed":
            raise ValueError(f"Ticket #{ticket.ticket_id} is closed and cannot be queued")
        if ticket.priority <= URGENT_PRIORITY_LIMIT:
            heapq.heappush(self._urgent, ticket)
        else:
            self._regular.append(ticket)

    def next_ticket(self) -> Ticket | None:
        """Return the next ticket, or None when both queues are empty (no crash)."""
        if self._urgent:
            return heapq.heappop(self._urgent)
        if self._regular:
            return self._regular.popleft()
        return None

    @property
    def sizes(self) -> tuple[int, int]:
        """(urgent, regular) - a short fixed record, so a tuple."""
        return len(self._urgent), len(self._regular)

    def __len__(self) -> int:
        return len(self._urgent) + len(self._regular)


# ---------- tuples and unpacking ----------

def split_location(location: str) -> tuple[str, tuple[str, ...]]:
    """'HQ / Floor 3 / Room 310' -> ('HQ', ('Floor 3', 'Room 310'))."""
    building, *details = [part.strip() for part in location.split("/")]
    return building, tuple(details)


def summary_row(ticket: Ticket) -> tuple[int, str, str, str]:
    """A fixed, read-only record for printing: (id, category, priority, status)."""
    return ticket.ticket_id, ticket.category, ticket.priority_label, ticket.status


# ---------- dicts: grouping and counting ----------

def count_by_category(tickets: Iterable[Ticket]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ticket in tickets:
        counts[ticket.category] = counts.get(ticket.category, 0) + 1
    return counts


def group_by_technician(tickets: Iterable[Ticket]) -> dict[str, list[Ticket]]:
    """Open tickets per technician. Unassigned tickets go under 'unassigned'."""
    groups: dict[str, list[Ticket]] = {}
    for ticket in tickets:
        if ticket.status == "closed":
            continue
        groups.setdefault(ticket.assigned_to or "unassigned", []).append(ticket)
    return groups


# ---------- sets ----------

def active_buildings(tickets: Iterable[Ticket]) -> set[str]:
    """Buildings that have at least one ticket which is not closed."""
    buildings: set[str] = set()
    for ticket in tickets:
        if ticket.status != "closed":
            building, _ = split_location(ticket.location)
            buildings.add(building)
    return buildings


def reporter_overlap(tickets: list[Ticket]) -> dict[str, set[str]]:
    """Compare reporters of urgent tickets with reporters of network tickets."""
    urgent = {t.reporter_email for t in tickets if t.priority <= URGENT_PRIORITY_LIMIT}
    network = {t.reporter_email for t in tickets if t.category == "network"}
    return {
        "both": urgent & network,
        "either": urgent | network,
        "urgent_not_network": urgent - network,
    }


# ---------- comprehensions ----------

def open_tickets(tickets: Iterable[Ticket]) -> list[Ticket]:
    return [t for t in tickets if t.status != "closed"]


def departments(employees: Iterable[Employee]) -> set[str]:
    return {e.department for e in employees}


def title_index(tickets: Iterable[Ticket]) -> dict[int, str]:
    return {t.ticket_id: t.title for t in tickets}


# ---------- sorting and key functions ----------

def age_key(ticket: Ticket):
    """Regular key function: oldest ticket first."""
    return ticket.created_at


def sort_by_age(tickets: Iterable[Ticket]) -> list[Ticket]:
    return sorted(tickets, key=age_key)


def sort_by_deadline(tickets: Iterable[Ticket]) -> list[Ticket]:
    return sorted(tickets, key=lambda t: t.due_at)


def sort_for_report(tickets: Iterable[Ticket]) -> list[Ticket]:
    """Two fields: by category name, then the most urgent first inside it."""
    return sorted(tickets, key=lambda t: (t.category, t.priority))


def average_hours_open(tickets: Iterable[Ticket], now) -> float:
    """Average time (hours) that tickets which are not closed have been waiting."""
    hours = [t.hours_open(now) for t in tickets if t.status != "closed"]
    if not hours:
        return 0.0
    return round(sum(hours) / len(hours), 1)
