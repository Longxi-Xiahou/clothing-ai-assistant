from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.repositories.mysql.users import MySQLUserRepository
from app.repositories.mysql.preferences import MySQLPreferenceRepository
from app.schemas.user import UserCreate, UserRead
from app.schemas.preference import PreferenceRead, PreferenceWrite

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    repository = MySQLUserRepository(db)
    try:
        return repository.create(payload.model_dump())
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this external_id already exists.",
        )


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = MySQLUserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


@router.get(
    "/{user_id}/preferences",
    response_model=PreferenceRead,
)
def get_user_preferences(
    user_id: int,
    db: Session = Depends(get_db),
):
    if MySQLUserRepository(db).get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    preference = MySQLPreferenceRepository(db).get_by_user_id(user_id)
    if preference is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User preferences have not been created yet.",
        )
    return preference


@router.put(
    "/{user_id}/preferences",
    response_model=PreferenceRead,
)
def upsert_user_preferences(
    user_id: int,
    payload: PreferenceWrite,
    db: Session = Depends(get_db),
):
    if MySQLUserRepository(db).get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return MySQLPreferenceRepository(db).save(
        user_id,
        payload.model_dump(),
    )
