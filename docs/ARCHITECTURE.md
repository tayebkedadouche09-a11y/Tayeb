# Tayeb Construction ERP Architecture

## Components

1. ERP Core: Frappe/ERPNext v16 construction operations from BuildSuite Core.
2. Commercial Suite: Frappe/ERPNext v15 construction modules kept as an isolated compatibility/reference component until migrated to v16.
3. BIM Engine: OpenConstructionERP component kept isolated because it is AGPL-3.0 and uses a different FastAPI/React/PostgreSQL stack.
4. Tayeb Integration Gateway: the integration boundary owned by this project.

## Business flow

Drawing / IFC / PDF -> BIM takeoff -> quantities -> BOQ -> rate analysis -> estimate -> budget -> procurement -> site execution -> progress -> billing -> cost/profit.

## Rule

The ERP core remains the system of record for projects, BOQ, workforce, equipment, procurement, site execution and finance. BIM is an engineering service boundary, not a second ERP database.
