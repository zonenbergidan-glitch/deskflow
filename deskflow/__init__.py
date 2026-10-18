"""DeskFlow - an IT helpdesk ticket system (Advanced Programming course, stage 1)."""

from .models import (
    Employee,
    Helpdesk,
    HardwareTicket,
    NetworkTicket,
    SoftwareTicket,
    Technician,
    Ticket,
)

__all__ = [
    "Employee",
    "Helpdesk",
    "HardwareTicket",
    "NetworkTicket",
    "SoftwareTicket",
    "Technician",
    "Ticket",
]

__version__ = "0.1.0"
