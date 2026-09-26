# Tayeb Construction ERP

Tayeb is a construction-company ERP architecture combining project operations, BOQ/estimating, site execution, commercial controls, and BIM/takeoff through clear service boundaries.

## Included components

- `components/erp-core` — BuildSuite Core / Frappe ERPNext v16
- `components/commercial-suite` — Construction Management Suite / Frappe ERPNext v15
- `components/bim-engine` — OpenConstructionERP / BIM, CAD, takeoff and 4D/5D services
- `services/integration-gateway` — Tayeb-owned API boundary between ERP and BIM

## Start

```bash
git clone --recurse-submodules https://github.com/tayebkedadouche09-a11y/Tayeb.git
cd Tayeb
./scripts/bootstrap.sh
```

The commercial-suite component is intentionally isolated until its v15 models are migrated and tested against ERPNext/Frappe v16.

See `docs/ARCHITECTURE.md` and `THIRD_PARTY_NOTICES.md`.


## Commercial architecture status

Tayeb now contains a first commercial application layer covering projects, tasks, BOQ, labour, attendance, equipment, materials/inventory movements, procurement, subcontractors, site reports, billing/retention, cash flow, audit logging and a BIM job boundary. The UI is Arabic/RTL and the API supports optional bearer-token protection through `TAYEB_API_TOKEN`.

### Production deployment
1. Set a strong `TAYEB_API_TOKEN`.
2. Set `TAYEB_BIM_URL` to the protected BIM service.
3. Mount persistent storage for `TAYEB_DB_PATH`.
4. Put the service behind HTTPS/reverse proxy.
5. Run `pytest -q` and the GitHub CI workflow before each release.

### Product boundary
The MIT reference applications remain documented separately. The AGPL BIM reference remains isolated; this repository does not copy its implementation into the Tayeb application layer. The BIM boundary is an integration contract so a compliant implementation or separately licensed engine can be connected.
