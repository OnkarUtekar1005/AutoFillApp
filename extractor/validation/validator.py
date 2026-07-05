"""
Validate mapped AOC-4 fields.
Returns a list of issues (not exceptions) so the pipeline can continue.
"""
import re
from extractor.mapping.schema import MANDATORY_FIELDS, FIELD_BY_KEY


def validate(fields: dict[str, dict]) -> dict:
    """
    fields: { field_key: {"value": ..., "confidence": ..., ...} }

    Returns:
      {
        "missing_mandatory": [field_key, ...],
        "low_confidence": [field_key, ...],
        "type_errors": [(field_key, reason), ...],
        "balance_check": None | "PASS" | "FAIL: <reason>",
      }
    """
    missing_mandatory = [
        key for key in MANDATORY_FIELDS
        if key not in fields or not fields[key].get("value")
    ]

    low_confidence = [
        key for key, info in fields.items()
        if info.get("confidence") == "LOW"
    ]

    type_errors = []
    for key, info in fields.items():
        fdef = FIELD_BY_KEY.get(key)
        if not fdef:
            continue
        value = str(info.get("value", ""))
        if fdef.data_type == "numeric":
            cleaned = re.sub(r'[,\s]', '', value)
            try:
                float(cleaned)
            except ValueError:
                type_errors.append((key, f"Expected numeric, got '{value}'"))
        elif fdef.data_type == "date":
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                type_errors.append((key, f"Expected YYYY-MM-DD, got '{value}'"))
        elif fdef.data_type == "enum" and fdef.enum_values:
            if value.lower() not in [e.lower() for e in fdef.enum_values]:
                type_errors.append((key, f"'{value}' not in {fdef.enum_values}"))

    # Balance sheet check: Assets ≈ Equity + Liabilities
    balance_check = None
    try:
        assets = _num(fields, "total_assets")
        liab_equity = _num(fields, "total_liabilities_equity")
        if assets and liab_equity:
            diff = abs(assets - liab_equity)
            pct = diff / max(abs(assets), 1) * 100
            if pct < 1.0:
                balance_check = "PASS"
            else:
                balance_check = f"FAIL: Assets={assets:,.0f} vs L+E={liab_equity:,.0f} ({pct:.1f}% diff)"
    except Exception:
        pass

    # P&L sanity: Revenue - Expenses ≈ PBT
    pnl_check = None
    try:
        revenue = _num(fields, "total_income")
        expenses = _num(fields, "total_expenses")
        pbt = _num(fields, "profit_before_tax")
        if revenue and expenses and pbt:
            calc_pbt = revenue - expenses
            diff = abs(calc_pbt - pbt)
            pct = diff / max(abs(pbt), 1) * 100
            if pct < 5.0:
                pnl_check = "PASS"
            else:
                pnl_check = (
                    f"FAIL: Revenue({revenue:,.0f}) - Expenses({expenses:,.0f})"
                    f" = {calc_pbt:,.0f} but PBT={pbt:,.0f} ({pct:.1f}% diff)"
                )
    except Exception:
        pass

    return {
        "missing_mandatory": missing_mandatory,
        "low_confidence": low_confidence,
        "type_errors": type_errors,
        "balance_check": balance_check,
        "pnl_check": pnl_check,
    }


def _num(fields: dict, key: str) -> float | None:
    info = fields.get(key)
    if not info:
        return None
    try:
        return float(re.sub(r'[,\s]', '', str(info["value"])))
    except (ValueError, TypeError):
        return None
