# Tayeb Construction ERP

Tayeb is a construction-company ERP architecture combining project operations, BOQ/estimating, site execution, commercial controls, and BIM/takeoff through clear service boundaries.

## Included components

- `components/erp-core` — BuildSuite Core / Frappe ERPNext v16
- `components/commercial-suite` — Construction Management Suite / Frappe ERPNext v15
- `components/bim-engine` — OpenConstructionERP / BIM, CAD, takeoff and 4D/5D services
- `services/integration-gateway` — Tayeb-owned API boundary between ERP and BIM
- `app` — Tayeb-owned FastAPI application layer

## Start

```bash
git clone --recurse-submodules https://github.com/tayebkedadouche09-a11y/Tayeb.git
cd Tayeb
./scripts/bootstrap.sh
```

The commercial-suite component is intentionally isolated until its v15 models are migrated and tested against ERPNext/Frappe v16.

## Application layer

The Tayeb-owned application currently covers projects, tasks, BOQ, labour, attendance, equipment, materials/inventory movements, procurement, subcontractors, site reports, billing/retention, cash flow, cost entries, audit logging and a BIM job boundary. It also includes local authentication with roles: owner, admin, project_manager, engineer, accountant, site_manager and viewer, plus basic double-entry accounting, payroll approval journals, purchase-receipt journals, billing-payment journals, budgets and budget-vs-actual reporting.

### Authentication

For a first deployment, set:

```bash
export TAYEB_AUTH_SECRET='use-a-long-random-secret'
export TAYEB_BOOTSTRAP_PASSWORD='use-a-long-password'
```

On first startup, the bootstrap password creates the local `owner` account. Login is available at `POST /api/auth/login`. The returned bearer token is valid for 12 hours. After login, owner/admin users can create additional users through `POST /api/auth/users`.

For compatibility, `TAYEB_API_TOKEN` can still be used as a legacy owner-level service token. Do not expose the service publicly without HTTPS.

### Production deployment

1. Set strong `TAYEB_AUTH_SECRET` and `TAYEB_BOOTSTRAP_PASSWORD`.
2. Set `TAYEB_BIM_URL` to the protected BIM service.
3. Mount persistent storage for `TAYEB_DB_PATH`.
4. Put the service behind HTTPS/reverse proxy.
5. Run `pytest -q` and the GitHub CI workflow before each release.
6. Back up the database before schema or deployment changes.

### Product boundary

The MIT reference applications remain documented separately. The AGPL BIM reference remains isolated; this repository does not copy its implementation into the Tayeb application layer. The BIM boundary is an integration contract so a compliant implementation or separately licensed engine can be connected.

## Current status

This is an active construction ERP foundation, not a claim that every enterprise module is finished. The current accounting layer is a foundation: chart of accounts, balanced journals, posting, trial balance and a basic profit-and-loss report are implemented. Budgeting and several operational-to-accounting integrations are also present. Fiscal periods/closing and basic invoice tax/retention accounting are included. Reversals, jurisdiction-specific VAT rules, full document lifecycle/versioning, migrations, production BIM processing, advanced scheduling and deeper enterprise workflows remain future implementation work.


## Finance controls added

The application now includes:
- supplier invoices and supplier payment lifecycle with AP/cash journals;
- payroll allocation from approved payroll items to projects;
- budget version snapshots;
- posted journal reversal with an auditable reversal link;
- project operational-cost vs posted-accounting-expense reconciliation;
- balance-sheet account balances;
- document upload metadata (MIME type, size, SHA-256 checksum) with the existing 25 MB limit.

These controls are additive to the existing construction workflow: projects → BOQ → progress → procurement/materials → labour/equipment → billing → collections → accounting.

### Accounting scope

The accounting layer is a construction-oriented operational ledger, not a jurisdiction-specific statutory accounting package. Tax/VAT rates, returns, withholding, payroll statutory deductions, multi-currency, year-end closing entries, and local Algerian reporting still require a dedicated localization layer and validation before production statutory use.

### Verification status

CI is configured in `.github/workflows/ci.yml`. The GitHub API did not report a workflow run for the latest commit at the time of this update, so the new test suite has **not** been claimed as passing. Run `cd app && pip install -r requirements.txt && pytest -q` locally or wait for the repository's Actions runner to execute the push workflow.
