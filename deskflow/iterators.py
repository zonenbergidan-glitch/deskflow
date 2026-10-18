"""A custom Iterable/Iterator, generator functions and a lazy pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from .models import Ticket


class TicketBoard:
    """Iterable collection of tickets, as shown on the helpdesk board.

    Iteration order: the order in which tickets were added to the board.
    Every call to iter(board) returns a NEW TicketBoardIterator.
    """

    def __init__(self, tickets: Iterable[Ticket] = ()) -> None:
        self._tickets: list[Ticket] = list(tickets)

    def add(self, ticket: Ticket) -> None:
        self._tickets.append(ticket)

    def __len__(self) -> int:
        return len(self._tickets)

    def __iter__(self) -> TicketBoardIterator:
        return TicketBoardIterator(self._tickets)


class TicketBoardIterator:
    """Holds the iteration state (current index) separately from the board."""

    def __init__(self, tickets: list[Ticket]) -> None:
        self._tickets = tickets
        self._index = 0

    def __iter__(self) -> TicketBoardIterator:
        return self

    def __next__(self) -> Ticket:
        if self._index >= len(self._tickets):
            raise StopIteration
        ticket = self._tickets[self._index]
        self._index += 1
        return ticket


def iter_overdue(tickets: Iterable[Ticket], now: datetime) -> Iterator[Ticket]:
    """Generator: yields, one by one, open tickets that missed their SLA."""
    for ticket in tickets:
        if ticket.is_overdue(now):
            yield ticket


def traced(tickets: Iterable[Ticket], seen: list[int]) -> Iterator[Ticket]:
    """Generator that records every ticket id it hands out (to show laziness)."""
    for ticket in tickets:
        seen.append(ticket.ticket_id)
        yield ticket


def urgent_unassigned_pipeline(tickets: Iterable[Ticket]) -> Iterator[int]:
    """Lazy 3-stage pipeline built from generator expressions.

    1. filter: tickets that are still open (status == 'open')
    2. filter: urgent (priority 1-2) and not yet assigned
    3. map:    return only the ticket id

    No intermediate lists are created. Nothing runs until someone asks
    for the first value.
    """
    still_open = (t for t in tickets if t.status == "open")
    urgent = (t for t in still_open if t.priority <= 2 and t.assigned_to is None)
    return (t.ticket_id for t in urgent)
