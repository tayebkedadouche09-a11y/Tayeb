# Tayeb Integration Gateway

A small API boundary between the Frappe ERP and the BIM/takeoff service.

The gateway deliberately does not copy BIM engine source code into the ERP app. Configure the BIM service URL with `TAYEB_BIM_URL`.

## Endpoints

- GET /health
- GET /api/v1/config
- POST /api/v1/bim/jobs

The BIM job endpoint forwards a JSON job request to the configured BIM service.
