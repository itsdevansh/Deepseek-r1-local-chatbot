from fastapi import FastAPI
from app.routers import auth, user, chat
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (You can specify specific domains here)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(chat.router)

# Initialize database connection


@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI Auth System"}
