from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from app.utils.security import authenticate_user, get_password_hash
from app.utils.jwt import create_access_token
from app.database import db
from app.schemas.user import Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def register_user(user: dict):
    existing_user = await db["users"].find_one({"username": user["username"]})
    if existing_user:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )
    user_data = {
        "username": user["username"],
        "email": user["email"],
        "password": get_password_hash(user["password"])
    }
    await db["users"].insert_one(user_data)
    user = await authenticate_user(user["username"], user["password"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        access_token = create_access_token(data={"sub": user["username"]})
        del user["_id"]
        del user["password"]
        return {"user": user, "token": access_token}


@router.post("/login", response_model=dict)
async def login_for_access_token(credentials: dict):
    user = await authenticate_user(credentials["username"], credentials["password"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        access_token = create_access_token(data={"sub": credentials["username"]})
        del user["_id"]
        del user["password"]
        return {"user": user, "token": access_token}
