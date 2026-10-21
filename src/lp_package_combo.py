import json
from decimal import Decimal
from pathlib import Path
from rapidfuzz import fuzz
from .lp_models import LPItem
from .extraction_models import ExtractedEntryDocuments, Package, PackingItem
from .generation_models import EntryPackage
from typing import TypedDict

class ItemGroup(TypedDict):
    lp_items: list[LPItem]
    pl_items: list[PackingItem]

# ratio = fuzz.ratio("GALLANT; NEW GALLANT BRAND TYRES SIZE 11R22.5 18PR 149/146L GL601-100PCS; SHANDONG; UN; 1; 11; 100; 22.5; 11R22.5; GL601; 48Kilogram; 1;","GALLANT 11R22.5 18PR 149/146 L GL601")
# print(ratio)

def load_lp_json():
    """Return the parsed contents of lp.json beside this script."""
    with Path(__file__).with_name("lp.json").open(encoding="utf-8") as file:
        return json.load(file)


def load_entry_docs_json():
    """Return the parsed contents of entry_docs.json beside this script."""
    with Path(__file__).with_name("entry_docs.json").open(encoding="utf-8") as file:
        return json.load(file)

lp_json = load_lp_json()
lp_items: list[LPItem] = [LPItem.model_validate(item) for item in lp_json]
entry_docs_json = load_entry_docs_json()
entry_docs: ExtractedEntryDocuments = ExtractedEntryDocuments.model_validate(entry_docs_json)

pl_items = entry_docs.packing_list.line_items

# Match container and numeric quantity, preserving duplicates and unmatched rows.
items_by_container_and_qty:dict[tuple[str,Decimal], ItemGroup] = {}
for item in lp_items:
    key = (item.container_no, Decimal(item.actual_qty.replace(",", "").strip()))
    group = items_by_container_and_qty.setdefault(key, {"lp_items": [], "pl_items": []})
    group["lp_items"].append(item)

for item in pl_items:
    key = (item.container_no, Decimal(item.qty.replace(",", "").strip()))
    group = items_by_container_and_qty.setdefault(key, {"lp_items": [], "pl_items": []})
    group["pl_items"].append(item)

items_by_container_and_qty = dict(sorted(items_by_container_and_qty.items()))

confirmed_packages: list[EntryPackage] = []
for key in items_by_container_and_qty.keys():
    lp_items = items_by_container_and_qty[key]["lp_items"]
    pl_items = items_by_container_and_qty[key]["pl_items"]


    if len(lp_items) == len(pl_items):
        if len(lp_items) == 1:
            package = EntryPackage(
                code=pl_items[0].package.code,
                qty=pl_items[0].package.qty,
                description = pl_items[0].name,
                marks=f"1 x {pl_items[0].container_no}",
                uniq_lp=lp_items[0].uniq_lp_ref,
                lp_actual_wt=lp_items[0].actual_wt
            )
            confirmed_packages.append(package)
        else: # if the aligned plxlp items are greater than 1
            #check if lp_descriptions are unique:
            first_description = lp_items[0].description_goods
            similar = True
            for i in range(1, len(lp_items)):
                current_item = lp_items[i]
                if current_item.description_goods != first_description:
                    similar = False
                    break

            #if lp_descriptions are unique:
            if not similar:
                available_pl_items = pl_items.copy()
                for lp_item in lp_items:
                    # Compare unused candidates; ties keep the first packing row.
                    best_pl_item = max(
                        available_pl_items,
                        key=lambda pl_item: fuzz.ratio(
                            lp_item.description_goods, pl_item.name
                        ),
                    )
                    available_pl_items.remove(best_pl_item)
                    package = EntryPackage(
                        code=best_pl_item.package.code,
                        qty=best_pl_item.package.qty,
                        description=best_pl_item.name,
                        marks=f"1 x {best_pl_item.container_no}",
                        uniq_lp=lp_item.uniq_lp_ref,
                        lp_actual_wt=lp_item.actual_wt,
                    )
                    confirmed_packages.append(package)
            else:
                for i in range(len(lp_items)):
                    lp_item = lp_items[i]
                    pl_item = pl_items[i]
                    # Compare every candidate; ties keep the first packing row.
                    package = EntryPackage(
                        code=pl_item.package.code,
                        qty=lp_item.actual_qty,
                        description=pl_item.name,
                        marks=f"1 x {lp_item.container_no}",
                        uniq_lp=lp_item.uniq_lp_ref,
                        lp_actual_wt=lp_item.actual_wt,
                    )
                    confirmed_packages.append(package)
    else:
        if len(pl_items) > len(lp_items):
            print("Dropping the following from packing list: \n ")
            print(pl_items)
        else: # if lp items are greater
            print("The following were not in the packing list but will be considered: \n")
            print(lp_items)
            for i in range(len(lp_items)):
                lp_item = lp_items[i]
                # Compare every candidate; ties keep the first packing row.
                package = EntryPackage(
                    code="",
                    qty=lp_item.actual_qty,
                    description=lp_item.description_goods,
                    marks=f"1 x {lp_item.container_no}",
                    uniq_lp=lp_item.uniq_lp_ref,
                    lp_actual_wt=lp_item.actual_wt,
                )
                confirmed_packages.append(package)


output_path = Path(__file__).with_name("entry_items.json")
with output_path.open("w", encoding="utf-8") as output_file:
    json.dump(
        {"items": [package.model_dump(mode="json") for package in confirmed_packages]},
        output_file,
        indent=2,
        ensure_ascii=False,
    )

# output_path = Path(__file__).with_name("lp_package_combo_output.txt")
# with output_path.open("w", encoding="utf-8") as output_file:
#     for (container_no, qty), group in items_by_container_and_qty.items():
#         line = f"{container_no} | qty={qty} | {group}\n"
#         print(line)
#         print(line, file=output_file)
    
# ratio = fuzz.ratio("GALLANT; NEW GALLANT BRAND TYRES SIZE 11R22.5 18PR 149/146L GL601-100PCS; SHANDONG; UN; 1; 11; 100; 22.5; 11R22.5; GL601; 48Kilogram; 1;","GALLANT 11R22.5 18PR 149/146 L GL602")
# print(ratio)
