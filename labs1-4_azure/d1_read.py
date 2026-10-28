"""Lab 9, D1: read the 7 FreshCart files with Azure AI Document Intelligence (Lab 1, now in Azure).

    python d1_read.py                 read all 7 files and write read/<file>.md
    python d1_read.py --raw-excel     keep the spreadsheet as Document Intelligence returns it

Document Intelligence's layout model returns each file as text, with headings and tables kept. Lab 1's three
problems are checked at the end: the scanned PDF, the Word table's column names and the spreadsheet's header.
"""
import re             # take out the table markup once its rows are written as lines
import sys            # read --raw-excel
import time           # time each file

import pandas         # read the spreadsheet as data, the Lab 1 fix
from azure.ai.documentintelligence import DocumentIntelligenceClient          # Azure's document reader
from azure.ai.documentintelligence.models import DocumentContentFormat

from docs_common import RAW, READ, SIGN_IN, setting


def table_rows(table):
    """A table as one line per row, each cell named by its column: "Priority: P1; Trigger: ...". A row read alone
    still says what each value is, which is what search needs."""
    grid = {}
    for cell in table.cells:
        grid.setdefault(cell.row_index, {})[cell.column_index] = cell.content.strip()
    header = grid.get(0, {})
    return ["; ".join(f"{header.get(c, '')}: {v}" for c, v in sorted(row.items())) for r, row in sorted(grid.items()) if r > 0]


def read_excel_as_data(path):
    """The spreadsheet as rows, with the real header row (row 5 of the sheet, as in Lab 1) naming every value."""
    sheet = pandas.read_excel(path, header=4).dropna(how="all")
    notes = [str(v) for v in sheet.iloc[:, 0] if str(v).startswith("Note")]                # the note under the table
    rows = sheet[~sheet.iloc[:, 0].astype(str).str.startswith("Note")].dropna(how="all")
    lines = ["; ".join(f"{col}: {val}" for col, val in row.items() if str(val) != "nan") for _, row in rows.iterrows()]
    text = "Refund Claims Register, March 2024. " + "\n".join(lines)          # the title stays with the rows
    return text + ("\n\n" + "\n".join(notes) if notes else "")              # and the note under the table


def main():
    client = DocumentIntelligenceClient(setting("DOCINTEL_ENDPOINT"), SIGN_IN)   # signed in as you: no key
    READ.mkdir(exist_ok=True)
    texts = {}
    for path in sorted(RAW.iterdir()):
        start = time.time()
        result = client.begin_analyze_document("prebuilt-layout", body=path.read_bytes(),
                                               output_content_format=DocumentContentFormat.MARKDOWN).result()
        text = result.content
        if result.tables:                                  # each table as one named line per row, not markup
            text = re.sub(r"<table>.*?</table>", "", text, flags=re.S)
            for table in result.tables:
                text += "\n\n" + "\n".join(table_rows(table))
        if path.suffix == ".xlsx" and "--raw-excel" not in sys.argv:
            text = read_excel_as_data(path)              # a spreadsheet is data: read it as data
        (READ / (path.name + ".md")).write_text(text, encoding="utf-8")
        texts[path.name] = text
        print(f"{path.name:38} {len(text):5} characters, {len(result.pages or [])} pages, "
              f"{len(result.tables or [])} tables, {time.time() - start:.1f}s")

    print("\nLab 1's three problems, read again:")
    sop = texts["support_escalation_sop_scanned.pdf"]
    print(f"  Scanned PDF: {len(sop)} characters (Lab 1: 0). Starts: {sop.strip().splitlines()[0][:70]!r}")
    sla = texts["support_sla_matrix.docx"]
    print(f"  Word table: column names kept: {'First response TAT' in sla}. "
          f"{next((l for l in sla.splitlines() if 'food safety' in l.lower() and 'First response TAT:' in l), '(no row)')[:110]}")
    claims = texts["refund_claims_march_2024.xlsx"]
    print(f"  Spreadsheet: values named by column: {'Claim ID:' in claims}. {claims.splitlines()[2][:110] if len(claims.splitlines()) > 2 else ''}")


main()
