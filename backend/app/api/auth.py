from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import create_access_token, verify_password
from app.db.session import get_session
from app.models.entities import User
from app.schemas.api import LoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = Depends(get_session)) -> TokenOut:
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenOut(access_token=create_access_token(user.username, {"role": user.role}))
