from fastapi import HTTPException

def require_superadmin(user):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin privilege required")
    return user

def require_admin_or_superadmin(user):
    if user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin privilege required")
    return user

def require_parent_or_higher(user):
    if user.role not in ["parent", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Parent-level privilege required")
    return user

def require_child_or_higher(user):
    if user.role not in ["child", "parent", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Child-level privilege required")
    return user
