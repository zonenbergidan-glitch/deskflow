"""Business model for DeskFlow - an IT helpdesk ticket system.

Classes:
    Employee       - a person who reports tickets.
    Technician     - an IT person who handles tickets.
    Ticket (ABC)   - abstract base ticket with shared logic.
    HardwareTicket, SoftwareTicket, NetworkTicket - concrete ticket types.
    Helpdesk       - contains all tickets and technicians (composition).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

# 1 is the most urgent priority, 4 is the least urgent.
PRIORITY_LABELS = {1: "critical", 2: "high", 3: "medium", 4: "low"}

# Multiplies the base SLA of a ticket type: urgent tickets get less time.
PRIORITY_SLA_FACTOR = {1: 0.25, 2: 0.5, 3: 1.0, 4: 2.0}

STATUSES = ("open", "in_progress", "closed")

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


class Employee:
    """An employee who reports tickets. Identified by e-mail."""

    def __init__(self, email: str, name: str, department: str) -> None:
        self.email = email
        self.name = name
        self.department = department

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        value = str(value).strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError(f"Invalid e-mail address: {value!r}")
        self._email = value

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        value = str(value).strip()
        if not value:
            raise ValueError("Employee name cannot be empty")
        self._name = value

    @classmethod
    def from_ticket_record(cls, record: dict) -> Employee:
        """Build the reporter of a ticket from a raw JSON record."""
        return cls(record["reporter_email"], record["reporter_name"], record["department"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Employee):
            return NotImplemented
        return self.email == other.email

    def __hash__(self) -> int:
        return hash(self.email)

    def __str__(self) -> str:
        return f"{self.name} ({self.department})"

    def __repr__(self) -> str:
        return f"Employee(email={self.email!r}, name={self.name!r}, department={self.department!r})"


class Technician:
    """An IT technician. Can handle only the ticket categories in `skills`."""

    def __init__(self, tech_id: str, name: str, skills: set[str], max_open: int = 3) -> None:
        if not tech_id:
            raise ValueError("Technician id cannot be empty")
        if max_open < 1:
            raise ValueError("max_open must be at least 1")
        self.tech_id = tech_id
        self.name = name
        self.skills = set(skills)
        self.max_open = max_open
        self._assigned: list[int] = []

    @property
    def open_load(self) -> int:
        """Computed property: how many tickets the technician holds right now."""
        return len(self._assigned)

    @property
    def is_available(self) -> bool:
        return self.open_load < self.max_open

    @property
    def assigned_ids(self) -> tuple[int, ...]:
        return tuple(self._assigned)

    def can_handle(self, ticket: Ticket) -> bool:
        return ticket.category in self.skills

    def take(self, ticket: Ticket) -> None:
        if not self.can_handle(ticket):
            raise ValueError(f"{self.name} cannot handle {ticket.category} tickets")
        if not self.is_available:
            raise ValueError(f"{self.name} already holds {self.max_open} tickets")
        if ticket.ticket_id not in self._assigned:
            self._assigned.append(ticket.ticket_id)

    def release(self, ticket_id: int) -> None:
        if ticket_id in self._assigned:
            self._assigned.remove(ticket_id)

    def __str__(self) -> str:
        skills = ", ".join(sorted(self.skills))
        return f"{self.name} [{skills}] load {self.open_load}/{self.max_open}"

    def __repr__(self) -> str:
        return f"Technician(tech_id={self.tech_id!r}, name={self.name!r}, skills={sorted(self.skills)!r})"


class Ticket(ABC):
    """Abstract base ticket. Subclasses define the category and base SLA."""

    def __init__(
        self,
        ticket_id: int,
        title: str,
        reporter_email: str,
        priority: int,
        created_at: datetime,
        location: str,
        status: str = "open",
        assigned_to: str | None = None,
    ) -> None:
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            raise ValueError(f"ticket_id must be a positive integer, got {ticket_id!r}")
        self._ticket_id = ticket_id
        self.title = title
        self.reporter_email = reporter_email
        self.priority = priority
        self.created_at = created_at
        self.location = location
        self._status = "open"
        self.status = status
        self.assigned_to = assigned_to
        self.locked_by: str | None = None
        self.closed_at: datetime | None = None
        self.notes: list[str] = []
        self.work_seconds = 0.0

    # ----- abstract "contract" -----
    @property
    @abstractmethod
    def category(self) -> str:
        """Short category name, e.g. 'hardware'."""

    @property
    @abstractmethod
    def base_sla_hours(self) -> float:
        """Response time (hours) for a medium priority ticket of this type."""

    @abstractmethod
    def impact(self) -> str:
        """One line describing what the problem affects."""

    # ----- properties with validation -----
    @property
    def ticket_id(self) -> int:
        return self._ticket_id

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        value = str(value).strip()
        if len(value) < 3:
            raise ValueError("Ticket title must have at least 3 characters")
        self._title = value

    @property
    def priority(self) -> int:
        return self._priority

    @priority.setter
    def priority(self, value: int) -> None:
        if value not in PRIORITY_LABELS:
            raise ValueError(f"Priority must be one of {sorted(PRIORITY_LABELS)}, got {value!r}")
        self._priority = value

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS[self.priority]

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        if value not in STATUSES:
            raise ValueError(f"Status must be one of {STATUSES}, got {value!r}")
        if self._status == "closed" and value != "closed":
            raise ValueError(f"Ticket #{self.ticket_id} is closed and cannot be reopened")
        self._status = value

    # ----- shared business logic -----
    def sla_hours(self) -> float:
        return self.base_sla_hours * PRIORITY_SLA_FACTOR[self.priority]

    @property
    def due_at(self) -> datetime:
        """Computed property: the deadline according to the SLA."""
        return self.created_at + timedelta(hours=self.sla_hours())

    def is_overdue(self, now: datetime) -> bool:
        return self.status != "closed" and now > self.due_at

    def hours_open(self, now: datetime) -> float:
        end = self.closed_at or now
        return round((end - self.created_at).total_seconds() / 3600, 1)

    def close(self, note: str, when: datetime) -> None:
        self.status = "closed"
        self.closed_at = when
        self.notes.append(note)

    @staticmethod
    def parse_datetime(text: str) -> datetime:
        try:
            return datetime.strptime(text, DATETIME_FORMAT)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid date {text!r}, expected format YYYY-MM-DDTHH:MM") from None

    @classmethod
    def extra_fields(cls, data: dict) -> dict:
        """Fields that only a specific subclass needs. Overridden by subclasses."""
        return {}

    @classmethod
    def from_dict(cls, data: dict) -> Ticket:
        """Alternative constructor: create the right ticket type from a JSON dict.

        The type is chosen through the TICKET_TYPES mapping (no if/elif chain).
        """
        ticket_cls = TICKET_TYPES.get(data.get("category"))
        if ticket_cls is None:
            raise ValueError(f"Unknown category {data.get('category')!r}")
        try:
            return ticket_cls(
                ticket_id=data["id"],
                title=data["title"],
                reporter_email=data["reporter_email"],
                priority=data["priority"],
                created_at=Ticket.parse_datetime(data["created_at"]),
                location=data["location"],
                status=data.get("status", "open"),
                assigned_to=data.get("assigned_to"),
                **ticket_cls.extra_fields(data),
            )
        except KeyError as missing:
            raise ValueError(f"Missing field {missing}") from None

    # ----- dunder methods -----
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ticket):
            return NotImplemented
        return self.ticket_id == other.ticket_id

    def __hash__(self) -> int:
        return hash(self.ticket_id)

    def __lt__(self, other: Ticket) -> bool:
        """Used by heapq and sorted(): more urgent first, then earlier, then lower id."""
        return (self.priority, self.created_at, self.ticket_id) < (
            other.priority,
            other.created_at,
            other.ticket_id,
        )

    def __str__(self) -> str:
        return f"#{self.ticket_id} [{self.priority_label}] {self.category}: {self.title} ({self.status})"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(ticket_id={self.ticket_id}, priority={self.priority}, "
            f"status={self.status!r})"
        )


class HardwareTicket(Ticket):
    def __init__(self, *args, device: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.device = device

    @property
    def category(self) -> str:
        return "hardware"

    @property
    def base_sla_hours(self) -> float:
        return 24

    def impact(self) -> str:
        return f"one user's device: {self.device}"

    @classmethod
    def extra_fields(cls, data: dict) -> dict:
        return {"device": data["device"]}


class SoftwareTicket(Ticket):
    def __init__(self, *args, application: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.application = application

    @property
    def category(self) -> str:
        return "software"

    @property
    def base_sla_hours(self) -> float:
        return 48

    def impact(self) -> str:
        return f"application: {self.application}"

    @classmethod
    def extra_fields(cls, data: dict) -> dict:
        return {"application": data["application"]}


class NetworkTicket(Ticket):
    # From this number of affected users the ticket gets half the SLA time.
    WIDE_OUTAGE_USERS = 20

    def __init__(self, *args, affected_users: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.affected_users = affected_users

    @property
    def affected_users(self) -> int:
        return self._affected_users

    @affected_users.setter
    def affected_users(self, value: int) -> None:
        if not isinstance(value, int) or value < 1:
            raise ValueError(f"affected_users must be a positive integer, got {value!r}")
        self._affected_users = value

    @property
    def category(self) -> str:
        return "network"

    @property
    def base_sla_hours(self) -> float:
        return 8

    def sla_hours(self) -> float:
        """Override: a wide outage blocks many people, so it gets half the time."""
        hours = super().sla_hours()
        if self.affected_users >= self.WIDE_OUTAGE_USERS:
            hours /= 2
        return hours

    def impact(self) -> str:
        return f"{self.affected_users} users without network"

    @classmethod
    def extra_fields(cls, data: dict) -> dict:
        return {"affected_users": data["affected_users"]}


# Maps the "category" value in the data file to the class that handles it.
TICKET_TYPES: dict[str, type[Ticket]] = {
    "hardware": HardwareTicket,
    "software": SoftwareTicket,
    "network": NetworkTicket,
}


class Helpdesk:
    """The IT service desk. Contains (composition) tickets and technicians."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tickets: dict[int, Ticket] = {}
        self._technicians: dict[str, Technician] = {}

    # ----- tickets -----
    def add_ticket(self, ticket: Ticket) -> None:
        """Explicit decision: an existing id is an error, never a silent overwrite."""
        if ticket.ticket_id in self._tickets:
            raise ValueError(f"Ticket #{ticket.ticket_id} already exists")
        self._tickets[ticket.ticket_id] = ticket

    def remove_ticket(self, ticket_id: int) -> Ticket:
        ticket = self._tickets.pop(ticket_id, None)
        if ticket is None:
            raise ValueError(f"Ticket #{ticket_id} not found")
        if ticket.assigned_to in self._technicians:
            self._technicians[ticket.assigned_to].release(ticket_id)
        return ticket

    def find(self, ticket_id: int) -> Ticket | None:
        return self._tickets.get(ticket_id)

    @property
    def tickets(self) -> list[Ticket]:
        return list(self._tickets.values())

    # ----- technicians -----
    def add_technician(self, technician: Technician) -> None:
        if technician.tech_id in self._technicians:
            raise ValueError(f"Technician {technician.tech_id} already exists")
        self._technicians[technician.tech_id] = technician

    def technician(self, tech_id: str) -> Technician | None:
        return self._technicians.get(tech_id)

    @property
    def technicians(self) -> list[Technician]:
        return list(self._technicians.values())

    # ----- status changes -----
    def assign(self, ticket_id: int, tech_id: str) -> None:
        ticket = self.find(ticket_id)
        tech = self.technician(tech_id)
        if ticket is None or tech is None:
            raise ValueError(f"Unknown ticket #{ticket_id} or technician {tech_id}")
        if ticket.status == "closed":
            raise ValueError(f"Ticket #{ticket_id} is closed")
        tech.take(ticket)
        ticket.assigned_to = tech_id

    def close_ticket(self, ticket_id: int, note: str, when: datetime) -> None:
        ticket = self.find(ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket #{ticket_id} not found")
        ticket.close(note, when)
        if ticket.assigned_to in self._technicians:
            self._technicians[ticket.assigned_to].release(ticket_id)

    # ----- aggregates -----
    def count_by_status(self) -> dict[str, int]:
        counts = {status: 0 for status in STATUSES}
        for ticket in self._tickets.values():
            counts[ticket.status] += 1
        return counts

    def __len__(self) -> int:
        return len(self._tickets)

    def __contains__(self, ticket_id: object) -> bool:
        return ticket_id in self._tickets

    def __str__(self) -> str:
        return f"{self.name}: {len(self)} tickets, {len(self._technicians)} technicians"

    def __repr__(self) -> str:
        return f"Helpdesk(name={self.name!r}, tickets={len(self)})"
