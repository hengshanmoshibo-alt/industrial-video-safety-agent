from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.entities import Ticket, User, UserRole
from app.schemas.api import TicketCreate, TicketOut, TicketPatch

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    return session.exec(select(Ticket).order_by(Ticket.id.desc())).all()


@router.post("", response_model=TicketOut)
def create_ticket(
    payload: TicketCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    ticket = Ticket(**payload.model_dump(), created_by_id=actor.id)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int,
    payload: TicketPatch,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket
