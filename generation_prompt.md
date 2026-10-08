You will receive:

1. An entry-documents JSON containing `packing_list.line_items` and `import_declaration_form.line_items`.
2. An LP JSON array.

Transform these inputs into a JSON array of IDF items containing their associated packages.

Return only valid JSON, without Markdown fences, explanations, or introductory text.

## Output structure

Use exactly this structure and field order. All scalar values must be strings.
```json
[
  {
    "number": "",
    "idf_item_number": "",
    "idf_item_description": "",
    "total_gross_mass": "",
    "idf_net_mass": "",
    "total_qty": "",
    "idf_qty": "",
    "unit_fob": "",
    "total_fob": "",
    "generation_remarks": "",
    "packages": [
      {
        "code": "",
        "qty": "",
        "description": "",
        "marks": "",
        "uniq_lp": "",
        "lp_actual_wt": ""
      }
    ]
  }
]
```

## 1. Normalize values for comparison

- Compare numeric values using decimal arithmetic, ignoring thousands separators and insignificant trailing decimal zeros.
- Compare container numbers after trimming whitespace and converting to uppercase.
- For product matching, normalize capitalization, spacing, punctuation, and equivalent specification ordering.
- Normalization is for comparison only. Preserve source descriptions exactly in the output.
- Missing values are not equivalent to zero.

## 2. Assign LP rows to packing-list rows

Process packing-list rows in their original array order.

For each packing-list row, find unused LP rows satisfying both:

- LP `container_no` equals packing-list `container_no`.
- LP `actual_qty` numerically equals packing-list `qty`.

If multiple LP rows qualify, use the description_goods in the lp json item to match, otherwise assign the first unused qualifying row in the original LP array order.

Each packing-list row receives at most one LP row. Each LP row is used at most once.

Do not use LP `declared_qty` for this comparison. Do not use repeated container or reference-group weights as individual-item weights.

Do not present alternative LP assignments. Resolve ties sequentially as instructed.

Retain LP rows that have no packing-list match for subsequent IDF matching.

## 3. Match products to IDF items

For each assigned packing-list row, identify the corresponding IDF item using the product identity expressed in their descriptions.

Compare all available identifying attributes, including:

- Product type, such as tyre, tube, or flap.
- Brand.
- Size or dimensions.
- Model, pattern, or part number.
- Grade, rating, or other distinguishing specifications.

Require agreement on identifying attributes present in both descriptions. Harmless formatting differences are acceptable; conflicting sizes, brands, models, or product types are not.

Do not select a match merely because it is the closest-looking description.

Quantities need not be equal: one IDF item may cover multiple packing-list rows or containers. Quantity differences do not invalidate an otherwise clear product-identity match.

Several packing-list rows may map to the same IDF item.

If multiple IDF items remain indistinguishable, use explicit source references or other identifying evidence to resolve them. Do not assign IDF items sequentially merely to eliminate ambiguity.

## 4. Handle LP rows without packing-list matches

First attempt to match using item-specific information or explicit references in the LP row.

A generic shipment description does not identify an individual product.

If direct identification is unavailable, consider LP `actual_wt` numerically equalling IDF `net_mass` as supporting evidence only. Before accepting such a match, verify that:

- The candidate is unique among eligible IDF items.
- The records refer to comparable weight units and scope.
- Other available information supports the association.
- No product attributes contradict it.
- The association does not duplicate an allocation already accounted for.

Weight equality alone does not guarantee product identity. Do not infer product type from zero LP quantity.

If a match cannot be established, preserve the LP row as unresolved rather than inventing an IDF association.

## 5. Build package objects

For an LP row matched to a packing-list row:

- `code`: Copy packing-list `package.code`.
- `qty`: Copy packing-list `package.qty`.
- `description`: Copy packing-list `name` exactly.
- `marks`: Copy LP `container_no`.
- `uniq_lp`: Copy LP `uniq_lp_ref`.
- `lp_actual_wt`: Use LP `actual_wt`.

For an LP row without a packing-list match:

- `code`: `""`
- `qty`: Use LP `actual_qty`.
- `description`: `""`
- `marks`: Copy LP `container_no`.
- `uniq_lp`: Copy LP `uniq_lp_ref`.
- `lp_actual_wt`: Use LP `actual_wt`.

Do not substitute the IDF description for a missing packing-list description.

Preserve each LP row as a separate package, even when several rows share a container or `uniq_lp_ref`.

Remove thousands separators from numeric output values. Format `lp_actual_wt` to two decimal places.

## 6. Group and order

Create one object per matched IDF item containing all packages assigned to it.

Copy these fields directly from the IDF item:

- `idf_item_number`: `number`
- `idf_item_description`: Full `name`, without shortening or correcting it.
- `idf_net_mass`: `net_mass`
- `idf_qty`: `qty`

Exclude IDF items with no associated LP packages.

Order matched groups by IDF item number numerically.

Within groups, preserve the order obtained by traversing containers in their first appearance in the packing list, processing their packing-list rows in source order, then their unmatched LP rows in LP source order. Process LP-only containers afterward in LP source order.

For each unresolved LP package, append a separate object after the matched IDF groups. Leave its IDF fields, `unit_fob`, and `total_fob` empty. Preserve its package information and calculate its package totals normally.

Set `number` to sequential strings starting at `"1"` across all output objects.

## 7. Calculate values

Use decimal arithmetic.

For each group:

- `total_gross_mass` = sum of its packages’ `lp_actual_wt`.
- `total_qty` = sum of its packages’ `qty`.
- `unit_fob` = IDF `fob_value` ÷ IDF `qty`.
- `total_fob` = emitted `unit_fob` × `total_qty`.

Use IDF `fob_value`, not commercial-invoice values.

Do not sum packing-list container masses or LP `gross_wt` to calculate package gross mass.

Format `total_gross_mass` to two decimal places.

Calculate `unit_fob` with 28 significant digits and round-half-even where necessary. Calculate `total_fob` from the emitted `unit_fob` without additional rounding. Remove unnecessary trailing fractional zeros from these two fields.

If IDF quantity is zero or a required calculation input is missing, leave the affected calculated field empty. Do not invent values or silently treat missing values as zero.
## 8. Generation remarks

Populate `generation_remarks` with a concise explanation of any issues, uncertainties, or assumptions affecting the current output object.

Record, where applicable:

- Multiple eligible LP rows resolved through sequential assignment. Identify the affected packing-list and LP row numbers.
- Missing packing-list matches or unresolved IDF associations.
- Tentative matches, including the evidence used and any remaining uncertainty.
- Conflicting product attributes, such as brand, size, model, or product type.
- Missing, invalid, or zero values that prevent a required calculation.
- Missing package codes, quantities, descriptions, container numbers, or LP references.
- Any other issue that affects the completeness or reliability of the generated object.

Use source item numbers and field names to make each remark traceable. Refer to LP `number` when identifying individual LP rows, because `uniq_lp_ref` may repeat.

Do not flag expected structural differences as errors, such as multiple packages belonging to one IDF item or repeated container totals.

Include only issues relevant to the current object. Separate multiple remarks with semicolons. If no issues were encountered, return an empty string: `""`.

Preserve the source values and follow all existing matching and calculation rules. Do not change values merely to eliminate a remark.

## 9. Validate

Before returning the JSON:

- Account for every LP row exactly once.
- Confirm that sequential LP assignments respect container and quantity.
- Confirm that product matches contain no conflicting identifying attributes.
- Confirm that unresolved associations remain unresolved.
- Verify each group’s totals against its packages.
- Verify the FOB formulas.
- Preserve original descriptions exactly.
- Confirm sequential output numbering.
- Confirm that every scalar is a string and no extra fields exist.

Do not force a particular number of groups, packages, or totals. Derive them entirely from the inputs.

