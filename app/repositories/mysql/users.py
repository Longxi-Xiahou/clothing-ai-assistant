from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


class MySQLUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create(self, data: dict) -> User:
        user = User(**data)
        self.db.add(user)
        try:
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
            self.db.rollback()
            raise
