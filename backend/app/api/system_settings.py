import json

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SystemSetting, User
from app.security import require_roles
from app.utils import create_audit, safe_setting_value

router = APIRouter()

DEFAULT_SETTINGS = {
    "platform_sync_interval_minutes": ("integer", 5),
    "auto_create_tickets": ("boolean", True),
    "ticket_auto_assign": ("boolean", True),
    "require_response_approval": ("boolean", False),
}


@router.get("")
def get_settings(
    db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    rows = db.query(SystemSetting).filter(SystemSetting.admin_id == admin.id).all()
    stored = {
        row.setting_key: safe_setting_value(row.setting_value, row.setting_type)
        for row in rows
    }
    settings = {key: default for key, (_, default) in DEFAULT_SETTINGS.items()}
    settings.update(stored)
    return {"data": settings}


@router.put("")
def update_settings(
    request: Request,
    values: dict = Body(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    unsupported = set(values) - set(DEFAULT_SETTINGS)
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported settings: {', '.join(sorted(unsupported))}",
        )
    old_values = {}
    for key, value in values.items():
        expected, _ = DEFAULT_SETTINGS[key]
        if expected == "integer":
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > 1440
            ):
                raise HTTPException(
                    status_code=422, detail=f"{key} must be an integer from 1 to 1440"
                )
            serialized = str(value)
        elif expected == "boolean":
            if not isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"{key} must be a boolean")
            serialized = "true" if value else "false"
        else:
            serialized = json.dumps(value)
        setting = (
            db.query(SystemSetting)
            .filter_by(admin_id=admin.id, setting_key=key)
            .one_or_none()
        )
        old_values[key] = (
            safe_setting_value(setting.setting_value, setting.setting_type)
            if setting
            else DEFAULT_SETTINGS[key][1]
        )
        if setting is None:
            setting = SystemSetting(
                admin_id=admin.id, setting_key=key, setting_type=expected
            )
            db.add(setting)
        setting.setting_type = expected
        setting.setting_value = serialized
    create_audit(
        db,
        request,
        admin,
        "settings.updated",
        "system_settings",
        admin.id,
        old_values=old_values,
        new_values=values,
    )
    db.commit()
    return get_settings(db, admin)
