from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.auth import LoginRequest, TokenResponse
from ..services.auth import authenticate_admin, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_admin(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas.")
    return TokenResponse(access_token=create_access_token(user.username))
