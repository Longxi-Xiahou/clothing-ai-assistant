from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.preference import UserPreference


class MySQLPreferenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> UserPreference | None:
        return self.db.scalar(
            select(UserPreference).where(
                UserPreference.user_id == user_id
            )
        )

    def save(self, user_id: int, data: dict) -> UserPreference:
        preference = self.get_by_user_id(user_id)

        if preference is None:
            preference = UserPreference(user_id=user_id, **data)
            self.db.add(preference)
        else:
            for field, value in data.items():
                setattr(preference, field, value)

        self.db.commit()
        self.db.refresh(preference)
        return preference
