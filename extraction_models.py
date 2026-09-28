"""Application output structure defined in prompt_revamp.md."""

from pydantic import BaseModel, ConfigDict


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Package(ExtractionModel):
    type: str
    code: str
    qty: str

class InvoiceItem(ExtractionModel):
    number: str
    name: str
    qty: str
    package: Package
    unit_price: str
    total_price: str


class CommercialInvoice(ExtractionModel):
    incoterm: str
    currency: str
    fob_amount: str
    freight_amount: str
    line_items: list[InvoiceItem]
    serial_number: str
    extracted_remarks: str



class PackingItem(ExtractionModel):
    number: str
    name: str
    qty: str
    package: Package
    total_gross_mass: str
    total_net_mass: str


class PackingList(ExtractionModel):
    line_items: list[PackingItem]
    total_containers_x_size: list[str]
    extracted_remarks: str


class Party(ExtractionModel):
    name: str
    address: str
    country: str
    country_code: str


class CertificateOfOrigin(ExtractionModel):
    serial_number: str
    consignor: Party
    consignee: Party
    extracted_remarks: str


class ExtractedEntryDocuments(ExtractionModel):
    commercial_invoice: CommercialInvoice
    packing_list: PackingList
    certificate_of_origin: CertificateOfOrigin
