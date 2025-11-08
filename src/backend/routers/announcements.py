from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.collection import Collection
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from ..database import announcements_collection
from .auth import get_current_user

router = APIRouter(prefix="/announcements", tags=["announcements"])

class AnnouncementCreate(BaseModel):
    message: str = Field(..., min_length=1)
    expiration_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    expiration_date: Optional[str] = None
    start_date: Optional[str] = None

# Helper to serialize MongoDB docs
def serialize_announcement(doc):
    return {
        "id": str(doc.get("_id", "")),
        "message": doc["message"],
        "expiration_date": doc["expiration_date"],
        "start_date": doc.get("start_date"),
        "created_by": doc.get("created_by")
    }

@router.get("/", response_model=list)
def list_announcements():
    now = datetime.now().strftime("%Y-%m-%d")
    docs = announcements_collection.find({
        "expiration_date": {"$gte": now},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": now}}
        ]
    })
    return [serialize_announcement(doc) for doc in docs]

@router.post("/", status_code=201)
def add_announcement(data: AnnouncementCreate, user=Depends(get_current_user)):
    doc = {
        "message": data.message,
        "expiration_date": data.expiration_date,
        "start_date": data.start_date,
        "created_by": user.get("username") if user else None
    }
    try:
        result = announcements_collection.insert_one(doc)
        if not result.acknowledged:
            raise Exception("Insertion not acknowledged by database.")
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add announcement: {str(e)}")

@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    user=Depends(get_current_user)
):
    doc = announcements_collection.find_one({"_id": announcement_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    update_fields = {k: v for k, v in data.dict(exclude_unset=True).items()}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update.")
    announcements_collection.update_one({"_id": announcement_id}, {"$set": update_fields})
    return {"success": True}

@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, user=Depends(get_current_user)):
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    return {"success": True}

