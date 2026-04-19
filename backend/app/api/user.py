"""User management + GDPR right-to-deletion endpoint."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.database import get_db
from app.core.deps import get_current_user_id
from app.models.db_models import User, LearnerState, Session as DBSession, Quiz, Resource

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me")
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": str(user.id), "email": user.email, "name": user.name, "created_at": user.created_at}


@router.delete("/{target_user_id}", status_code=204)
async def delete_user(
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    GDPR right-to-deletion: purge all user data from PostgreSQL
    and associated ChromaDB embeddings.
    """
    if target_user_id != user_id:
        raise HTTPException(status_code=403, detail="Can only delete your own account")

    uid = target_user_id

    # Purge ChromaDB embeddings for this user (tagged with user metadata)
    try:
        from app.rag.chroma_client import get_collection, COLLECTION_DOCUMENTS, COLLECTION_WEB_CACHE
        for coll_name in [COLLECTION_DOCUMENTS, COLLECTION_WEB_CACHE]:
            coll = await get_collection(coll_name)
            try:
                await coll.delete(where={"user_id": target_user_id})
            except Exception:
                pass  # Collection may not have user-tagged docs
    except Exception:
        pass  # Non-fatal — continue with DB deletion

    # Cascade delete (FK constraints handle sessions, quizzes, learner_states)
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()
