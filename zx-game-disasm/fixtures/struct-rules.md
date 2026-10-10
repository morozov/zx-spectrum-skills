# Rules

## ROW: data rows

| ID | Rule | Enforcer | Question |
| --- | --- | --- | --- |
| ROW-1 | A data row's comment says what the row holds. | DATA_ECHO, review | Does this row open on its index? |
| ROW-2 | The key a table is indexed by is stated once. | — | |
| ROW-3 | A row comment never names a code range. | review | |
| ROW-4 | A sentence argues with no reading nobody offered. | FOIL | |
| ROW-5 | One spelling per word. | lint-terms, lint-nowhere | |
| ROW-6 | Persisted text records no history. | Vale NoDiary | |
| ROW-7 | Unused bytes carry no label for a used thing. | UNUSED_LABEL, review (candidate: FOIL) | |
| ROW-8 | A rename lands with its registry row. | review-record, review | |

## Other tables

| Term | Meaning |
| --- | --- |
| ID | Not a rule table: no Enforcer column. |
