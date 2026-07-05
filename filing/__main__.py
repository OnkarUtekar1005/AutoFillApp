"""
CLI: open an MCA V3 filing session for one client's extracted Excel.

  python -m filing --excel "D:\\Data\\finaloutput\\Acme_U27100MH2019PTC111111.xlsx"

Launches a headed browser at the MCA V3 portal, waits for you to log in, and
loads the client's cleaned field values ready to fill. Login, DSC signing, and
submit are always manual. See filing/aoc4_form.py for details.
"""
import argparse

from filing.aoc4_form import run_filing_session, MCA_V3_HOME_URL


def main():
    parser = argparse.ArgumentParser(description="Open an MCA V3 AOC-4 filing session.")
    parser.add_argument("--excel", required=True, help="Path to the client's finaloutput Excel")
    parser.add_argument("--url", default=MCA_V3_HOME_URL, help="MCA V3 URL to open")
    parser.add_argument("--headless", action="store_true", help="Run without a visible window (not recommended)")
    args = parser.parse_args()

    run_filing_session(args.excel, url=args.url, headed=not args.headless)


if __name__ == "__main__":
    main()
