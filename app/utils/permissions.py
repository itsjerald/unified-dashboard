from fastapi import HTTPException

def require_superadmin(user):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin privilege required")
    return user

def require_admin_or_superadmin(user):
    if user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin privilege required")
    return user

def require_parent(user):
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Parent privilege required")
    return user

def require_parent_or_spouse(user):
    if user.role not in ["parent", "spouse"]:
        raise HTTPException(status_code=403, detail="Parent or spouse privilege required")
    return user

def require_verified(user):
    if not user.is_verified:
        raise HTTPException(status_code=400, detail="User must be verified")
    return user

def require_child(user):
    if user.role != "child":
        raise HTTPException(status_code=403, detail="Child privilege required")
    return user
