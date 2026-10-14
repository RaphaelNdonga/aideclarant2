"""Pydantic models matching the JSON array in lp.json."""

from pydantic import BaseModel, ConfigDict, RootModel


class LPItem(BaseModel):
    """One LP row, preserving numeric strings and their original formatting."""

    model_config = ConfigDict(extra="forbid", strict=True)

    number: str
    uniq_lp_ref: str
    description_goods: str
    declared_qty: str
    gross_wt: str
    actual_qty: str
    actual_wt: str
    container_no: str


class LPItems(RootModel[list[LPItem]]):
    """The top-level LP array; validated rows are available through root."""
