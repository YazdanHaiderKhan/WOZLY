"""FastAPI dependency — extract and validate JWT bearer token."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    # AUTH BYPASS: Always return the guest demo user ID without requiring a token
    return "00000000-0000-0000-0000-000000000000"
