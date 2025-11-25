from fastapi import Request, HTTPException

def require_admin(request: Request):
    data = request.state.user_data
    if not data or data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not admin")

def require_parent_or_spouse(request):
    user = request.state.user_data
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user['role'] not in ['parent', 'spouse']:
        raise HTTPException(status_code=403, detail="Only parents or spouses can manage categories/rules.")
    return user