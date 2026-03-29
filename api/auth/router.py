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

@router.post("/sync", response_model=TokenResponse)
async def sync_oauth_user(body: dict, db: AsyncSession = Depends(get_db)):
    """Creates or retrieves user based on email, returns access token for OAuth signup"""
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Try to find existing user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    # If user doesn't exist, create new OAuth user
    if not user:
        user = User(email=email, hashed_password="oauth_user")
        db.add(user)
        await db.flush()
        
        # Create default settings for new user
        settings = UserSettings(user_id=user.id, notification_email=email)
        db.add(settings)
        await db.commit()
    else:
        await db.commit()
    
    await db.refresh(user)
    
    return TokenResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
        email=user.email,
    )
