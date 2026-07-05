/**
 * AOC-4 Test Form generator (Google Apps Script).
 *
 * HOW TO USE:
 *   1. Go to https://script.google.com and create a New project.
 *   2. Delete any sample code, paste this whole file, and Save.
 *   3. Select the function "createAOC4TestForm" and click Run.
 *      (Authorize it when Google asks — it only creates a Form in your Drive.)
 *   4. Open View > Logs (or Execution log). It prints the form's Edit URL and
 *      the live (published) URL. Open the live URL in Chrome to test filling.
 *
 * The question titles are the EXACT AOC-4 field labels, so the Claude browser
 * extension can locate each field by its label — the same way it will on the
 * real MCA portal. This is a safe rehearsal target, not the real MCA form.
 */
function createAOC4TestForm() {
  var form = FormApp.create('AOC-4 Test Form (mock)');
  form.setDescription('Mock AOC-4 form for testing autofill via the Claude browser extension. Not the real MCA portal.');
  form.setCollectEmail(false);

  var items = [
    {title: "Corporate Identification Number (CIN)", help: "cin (string)"},
    {title: "Name of the company", help: "company_name (string)"},
    {title: "Address of registered office", help: "registered_address (text)"},
    {title: "Financial year From", help: "financial_year_from (date)"},
    {title: "Financial year To", help: "financial_year_to (date)"},
    {title: "Date of Board meeting approving financial statements", help: "board_meeting_fs_date (date)"},
    {title: "FS Signatory 1 \u2014 DIN/PAN", help: "fs_sig1_din (string)"},
    {title: "FS Signatory 1 \u2014 Name", help: "fs_sig1_name (string)"},
    {title: "FS Signatory 1 \u2014 Designation", help: "fs_sig1_designation (string)"},
    {title: "Date of Board meeting approving Board's report (Sec 134)", help: "board_report_date (date)"},
    {title: "Date of signing of auditors' reports", help: "auditor_report_signing_date (date)"},
    {title: "Date of AGM", help: "agm_date (date)"},
    {title: "Name of auditor/firm", help: "auditor_name (string)"},
    {title: "Membership/registration number", help: "auditor_membership_number (string)"},
    {title: "Income-tax PAN of auditor/firm", help: "auditor_pan (string)"},
    {title: "Auditor City", help: "auditor_city (string)"},
    {title: "Auditor State/UT", help: "auditor_state (string)"},
    {title: "Share capital", help: "equity_share_capital (numeric)"},
    {title: "Reserves and surplus", help: "reserves_surplus (numeric)"},
    {title: "TOTAL EQUITY & LIABILITIES", help: "total_liabilities_equity (numeric)"},
    {title: "TOTAL ASSETS", help: "total_assets (numeric)"},
    {title: "Cash and cash equivalents", help: "cash_equivalents (numeric)"},
    {title: "Inventories", help: "inventories (numeric)"},
    {title: "Trade receivables", help: "trade_receivables (numeric)"},
    {title: "Revenue from Operations", help: "revenue_from_operations (numeric)"},
    {title: "Total Income", help: "total_income (numeric)"},
    {title: "Employee benefit expenses", help: "employee_benefits (numeric)"},
    {title: "Depreciation and amortization", help: "depreciation_amortization (numeric)"},
    {title: "Total expenses", help: "total_expenses (numeric)"},
    {title: "Profit before tax", help: "profit_before_tax (numeric)"},
    {title: "Profit/(Loss) for the period", help: "profit_after_tax (numeric)"}
  ];

  items.forEach(function (it) {
    form.addTextItem().setTitle(it.title).setHelpText(it.help);
  });

  Logger.log('Edit URL : ' + form.getEditUrl());
  Logger.log('Live URL : ' + form.getPublishedUrl());
}
