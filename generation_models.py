"""Strict JSON output models for generation_prompt.md."""
from pydantic import BaseModel, ConfigDict, RootModel


class GenerationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EntryPackage(GenerationModel):
    code: str
    qty: str
    description: str
    marks: str
    uniq_lp: str
    lp_actual_wt: str


class EntryItem(GenerationModel):
    number: str
    idf_item_number: str
    idf_item_description: str
    total_gross_mass: str
    idf_net_mass: str
    total_qty: str
    idf_qty: str
    unit_fob: str
    total_fob: str
    generation_remarks: str
    packages: list[EntryPackage]

class GeneratedEntryItems(GenerationModel):
    """Object wrapper required by OpenAI structured outputs."""

    items: list[EntryItem]
