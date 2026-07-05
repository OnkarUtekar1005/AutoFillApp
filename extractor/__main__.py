"""
CLI entry point.

Usage:
  python -m extractor <root_folder>
  python -m extractor <root_folder> --verbose
  python -m extractor <root_folder> --client "CompanyA Ltd" --period "2025-03-31"

<root_folder> should follow the structure:
  root/
    ClientName_L01234MH2020PTC123456/
      data/
        balance_sheet.pdf
        profit_loss.xlsx
        ...
      attachments/
        signed_balance_sheet.pdf
        ...

(Legacy client/date/files layouts without a CIN in the folder name are still
supported — see extractor/ingestion/folder_scanner.py.)
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="AOC-4 data extractor — extract financial data from client folders."
    )
    parser.add_argument("root", help="Root data folder containing client sub-folders")
    parser.add_argument("--verbose", action="store_true", help="Print per-file details")
    parser.add_argument("--client", help="Process only this client folder name")
    parser.add_argument("--period", help="Process only this period folder name")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="Print final JSON summary to stdout")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: Folder not found: {root}", file=sys.stderr)
        sys.exit(1)

    from extractor.ingestion.folder_scanner import scan_root
    from extractor.ingestion.pipeline import process_filing

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    filings = scan_root(root)

    if args.client:
        filings = [f for f in filings if args.client.lower() in f.client_name.lower()]
    if args.period:
        filings = [f for f in filings if args.period in f.period_label]

    if not filings:
        print("No matching filing folders found.", file=sys.stderr)
        sys.exit(1)

    results = []
    for filing in filings:
        result = process_filing(filing, root, verbose=args.verbose)
        results.append(result)

    print(f"\n{'='*60}")
    print(f"Processed {len(results)} filing(s).")
    for r in results:
        v = r["validation"]
        print(f"\n  {r['client_name']}  ({r.get('cin') or 'CIN not found'})  /  {r['period']}")
        print(f"    Status            : {r['status']}")
        print(f"    Fields extracted  : {r['total_fields_extracted']}")
        print(f"    Mandatory missing : {len(v['missing_mandatory'])}")
        if v["missing_mandatory"]:
            print(f"      > {', '.join(v['missing_mandatory'])}")
        print(f"    Low confidence    : {len(v['low_confidence'])}")
        if v.get("balance_check"):
            print(f"    Balance sheet     : {v['balance_check']}")
        if v.get("pnl_check"):
            print(f"    P&L check         : {v['pnl_check']}")
        print(f"    Attachments found : {len(r.get('attachments', []))}")
        print(f"    extracted.json    : {r['data_folder']}\\extracted.json")
        print(f"    Excel output      : {r['excel_path']}")

    if args.json_out:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
