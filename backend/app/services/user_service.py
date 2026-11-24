import uuid

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserPreferenceResponse,
    UserPreferenceUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)


class UserService:
    """Service handling user profile and preference management with strict data isolation."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        pref_repo: PreferenceRepository | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.pref_repo = pref_repo or PreferenceRepository()

    def get_profile(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)

    def update_profile(
        self,
        db: Session,
        user: User,
        req: UserUpdateRequest,
    ) -> UserResponse:
        updated_user = self.user_repo.update(db, user, full_name=req.full_name.strip())
        return UserResponse.model_validate(updated_user)

    def get_preferences(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> UserPreferenceResponse:
        pref = self.pref_repo.get_by_user_id(db, user_id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user_id)
        return UserPreferenceResponse.model_validate(pref)

    def update_preferences(
        self,
        db: Session,
        user_id: uuid.UUID,
        req: UserPreferenceUpdateRequest,
    ) -> UserPreferenceResponse:
        pref = self.pref_repo.get_by_user_id(db, user_id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user_id)

        update_data = req.model_dump(exclude_unset=True)
        updated_pref = self.pref_repo.update(db, pref, **update_data)
        return UserPreferenceResponse.model_validate(updated_pref)
