import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.core.dependencies import get_current_owner
from app.models import Owner
from app.schemas import (
    OwnerCreate,
    RefreshTokenBody,
    RefreshTokenResponse,
    RegisterResult,
    ResendVerificationBody,
    Token,
    VerifyEmailBody,
)
from app.services.email_service import send_verification_email
from app.services.rate_limit_async import allow_resend_verification
from app.services.refresh_token_service import (
    consume_and_rotate_refresh,
    issue_refresh_token,
    revoke_all_refresh_tokens,
)

router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Owner).filter(Owner.email == form_data.username))
    owner = result.scalars().first()

    if not owner or not verify_password(form_data.password, owner.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not owner.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Correo no verificado. Revisá tu bandeja o pedí un nuevo enlace.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": owner.email, "sub": str(owner.id)},
        expires_delta=access_token_expires,
        token_kind="access",
    )

    refresh_plain = await issue_refresh_token(owner.id)

    return {
        "access_token": access_token,
        "refresh": refresh_plain,
        "token_type": "bearer",
        "user": owner,
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(body: RefreshTokenBody):
    owner, new_refresh = await consume_and_rotate_refresh(body.refresh)
    if not owner or not owner.email_verified or not new_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    access_token = create_access_token(
        data={"email": owner.email, "sub": str(owner.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_kind="access",
    )
    return RefreshTokenResponse(access_token=access_token, refresh=new_refresh)


@router.post("/logout")
async def logout(current_owner: Owner = Depends(get_current_owner)):
    await revoke_all_refresh_tokens(current_owner.id)
    return {"ok": True}


@router.post("/register", response_model=RegisterResult)
async def register_owner(owner_in: OwnerCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Owner).filter(Owner.email == owner_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.now(timezone.utc)
    verified = bool(config.AUTO_VERIFY_EMAIL)
    v_token = None
    v_expires = None
    if not verified:
        v_token = secrets.token_urlsafe(24)
        v_expires = now + timedelta(hours=48)

    new_owner = Owner(
        name=owner_in.name,
        email=owner_in.email,
        phone=owner_in.phone,
        hashed_password=get_password_hash(owner_in.password),
        email_verified=verified,
        verification_token=v_token if not verified else None,
        verification_token_expires_at=v_expires,
    )
    db.add(new_owner)
    await db.commit()
    await db.refresh(new_owner)

    if verified:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"email": new_owner.email, "sub": str(new_owner.id)},
            expires_delta=access_token_expires,
            token_kind="access",
        )
        refresh_plain = await issue_refresh_token(new_owner.id)
        return RegisterResult(
            message="Cuenta creada. Ya podés iniciar sesión.",
            access_token=access_token,
            refresh=refresh_plain,
            user=new_owner,
        )

    await send_verification_email(new_owner.email, v_token, new_owner.name)

    return RegisterResult(
        message=(
            "Cuenta creada. Si SMTP está configurado, te enviamos un enlace al correo. "
            "Si no, revisá los logs del servidor o usá «Reenviar verificación»."
        ),
        user=new_owner,
    )


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    body: ResendVerificationBody,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not await allow_resend_verification(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Probá más tarde.",
        )

    result = await db.execute(select(Owner).filter(Owner.email == body.email))
    owner = result.scalars().first()
    if owner and not owner.email_verified:
        owner.verification_token = secrets.token_urlsafe(24)
        owner.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        await db.commit()
        await db.refresh(owner)
        await send_verification_email(owner.email, owner.verification_token, owner.name)

    return {
        "ok": True,
        "message": "Si el correo existe y falta verificarlo, enviamos nuevas instrucciones.",
    }


@router.post("/verify-email")
async def verify_email(body: VerifyEmailBody, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Owner).filter(
            and_(
                Owner.verification_token == body.token.strip(),
                Owner.verification_token_expires_at.isnot(None),
                Owner.verification_token_expires_at > now,
            )
        )
    )
    owner = result.scalars().first()
    if not owner:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    owner.email_verified = True
    owner.verification_token = None
    owner.verification_token_expires_at = None
    await db.commit()
    await revoke_all_refresh_tokens(owner.id)
    return {"ok": True, "message": "Correo verificado. Ya podés iniciar sesión."}
