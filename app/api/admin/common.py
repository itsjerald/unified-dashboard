from fastapi import Request, HTTPException

def require_admin(request: Request):
    data = request.state.user_data
    if not data or data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not admin")
