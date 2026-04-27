from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.models import Owner
from app.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

async def get_current_owner(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_kind") == "refresh":
            raise credentials_exception
        email: str = payload.get("email")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.PyJWTError:
        raise credentials_exception
    
    result = await db.execute(select(Owner).filter(Owner.email == token_data.email))
    owner = result.scalars().first()
    if owner is None:
        raise credentials_exception
    return owner
