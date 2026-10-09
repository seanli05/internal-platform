"""Pydantic schemas — the shape of your JSON.

Deliberately separate from models.py. The table is your storage contract;
these are your API contract. They drift apart fast (you will add a
`thumbnail_url` here that has no column, and a `deleted_at` column that
never appears here) — keeping them separate from day one costs nothing.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class PhotoOut(BaseModel):
    """What GET /photos returns for each row."""

    # Lets Pydantic read attributes off a SQLAlchemy object instead of
    # requiring a dict. Without it, returning a Photo instance fails.
    model_config = ConfigDict(from_attributes=True)

    id:int
    filename: str
    uploaded_at: datetime

    # Exactly the drift the docstring predicts: an API field with no column.
    # @computed_field puts this property into the JSON output. It's a path,
    # not a full URL: the client already knows the API's base URL and
    # prefixes it, so this stays correct behind proxies or a new domain.
    @computed_field
    @property
    def url(self) -> str:
        return f"/photos/{self.id}/file"
