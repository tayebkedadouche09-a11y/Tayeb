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
