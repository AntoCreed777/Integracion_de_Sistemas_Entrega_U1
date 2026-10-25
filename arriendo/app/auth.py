import os
from fastapi import Security, HTTPException, status, Depends
from fastapi.security.api_key import APIKeyHeader
from typing import Optional

API_KEYS = {
    os.environ["ADMIN_API_KEY"]: {"client": "Sistema Interno", "role": "admin"},
    os.environ["CLIENT_API_KEY"]: {"client": "Dashboard", "role": "readonly"},
}

api_key_header = APIKeyHeader(name="API-Key", auto_error=False)

def client_validation(key: Optional[str] = Security(api_key_header)):
    client_data = API_KEYS.get(key)
    if not client_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "API Key inválida o faltante"}
        )
    return client_data

def admin_validation(client_data: dict = Depends(client_validation)):
    if client_data["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No tienes permisos de escritura."}
        )
    return client_data