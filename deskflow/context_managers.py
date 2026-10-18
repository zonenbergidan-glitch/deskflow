"""Context manager for a technician's work session on a ticket."""

from __future__ import annotations

import time

from .models import Ticket


class TicketWorkSession:
    """Use with `with TicketWorkSession(ticket, "T1") as session:`.

    On enter:
        * locks the ticket so no other technician can work on it;
        * saves the previous status and marks the ticket 'in_progress';
        * starts a timer.
    On exit (always, also when an exception happens):
        * releases the lock;
        * adds the measured time to ticket.work_seconds;
        * on an exception: restores the previous status and writes a note.
    The exception is NOT suppressed (__exit__ returns False): hiding a failure
    would leave the technician thinking the work succeeded.
    """

    def __init__(self, ticket: Ticket, tech_id: str) -> None:
        self.ticket = ticket
        self.tech_id = tech_id
        self.previous_status: str | None = None
        self.duration_seconds = 0.0
        self.failed = False
        self._start = 0.0

    def __enter__(self) -> TicketWorkSession:
        if self.ticket.locked_by is not None:
            raise RuntimeError(
                f"Ticket #{self.ticket.ticket_id} is locked by {self.ticket.locked_by}"
            )
        self.previous_status = self.ticket.status
        self.ticket.status = "in_progress"  # raises ValueError for a closed ticket
        self.ticket.locked_by = self.tech_id
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.duration_seconds = time.perf_counter() - self._start
        self.ticket.work_seconds += self.duration_seconds
        self.ticket.locked_by = None
        if exc_type is not None:
            self.failed = True
            self.ticket.status = self.previous_status
            self.ticket.notes.append(f"work by {self.tech_id} failed: {exc}")
        return False
