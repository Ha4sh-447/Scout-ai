from api.auth.service import verify_password
from api.auth.schemas import LoginRequest
from db.models import UserSettings
from api.auth.service import create_access_token, hash_password
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED, HTTP_401_UNAUTHORIZED
from db.base import AsyncSessionLocal, get_db
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.auth.schemas import RegisterRequest, TokenResponse
from fastapi import APIRouter

from db.models import User

router = APIRouter(prefix='/auth', tags=['auth'])

@router.post("/register" , response_model=TokenResponse, status_code=HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing_user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email = body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.flush()

    settings = UserSettings(user_id=user.id, notification_email=body.email)
    db.add(settings)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
            access_token=create_access_token(user.id),
            user_id = user.id,
            email=user.email,
            )

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(hashed=user.hashed_password, plain=body.password):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return TokenResponse(
            access_token=create_access_token(user.id),
            user_id=user.id,
            email= user.email,
            )
