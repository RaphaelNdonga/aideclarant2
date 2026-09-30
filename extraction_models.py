"""Application output structure defined in prompt.md."""

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
    extraction_remarks: str


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
    extraction_remarks: str


class Party(ExtractionModel):
    name: str
    address: str

class CertificateParty(Party):
    country: str
    country_code: str

class Importer(Party):
    county_code: str

class CertificateOfOrigin(ExtractionModel):
    serial_number: str
    consignor: CertificateParty
    consignee: CertificateParty
    extraction_remarks: str

class ModeOfTransport(ExtractionModel):
    name: str
    code: str

class ImportDeclarationItem(ExtractionModel):
    number: str
    name: str
    qty: str
    qty_unit: str
    origin: str
    hs_code: str
    net_mass: str
    fob_value: str


class ImportDeclarationForm(ExtractionModel):
    no: str
    pin: str
    incoterm: str
    importer: Importer
    seller: Party
    mode_of_transport: ModeOfTransport
    line_items: list[ImportDeclarationItem]
    extraction_remarks: str


class BillOfLading(ExtractionModel):
    no: str
    place_of_delivery: str
    port_of_discharge: str
    vessel: str
    voyage_no: str
    extraction_remarks: str


class ExtractedEntryDocuments(ExtractionModel):
    commercial_invoice: CommercialInvoice
    packing_list: PackingList
    certificate_of_origin: CertificateOfOrigin
    import_declaration_form: ImportDeclarationForm
    bill_of_lading: BillOfLading
