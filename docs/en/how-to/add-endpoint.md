---
title: "Add API Ledger Endpoint"
description: "Steps to add a new endpoint to API Ledger, wire schema/handler, and quick test with curl."
icon: material/plus-network
---

# Add API Ledger Endpoint

## Goal

Step-by-step guide to adding a new endpoint to HieraChain's FastAPI router (Ledger), including Pydantic schema definition, writing a handler, updating the router, and quick testing with `curl`.

## Step 1: Prepare Schema (optional)

* Open `hierachain/api/ledger/schemas.py`.
* Add a Pydantic class if the endpoint needs a new payload, e.g.:

```python
class PingRequest(BaseModel):
  message: str

class PingResponse(BaseModel):
  ok: bool
  echo: str
```

## Step 2: Add Handler in Router

* Open `hierachain/api/ledger/router.py`.
* Import the schema (if any) and add a route to `APIRouter(prefix="/api/ledger", ...)`.

Example (descriptive):

```python
@router.post("/ping", response_model=PingResponse)
async def ping(req: PingRequest):
  return PingResponse(ok=True, echo=req.message)
```

Tip: use existing DI (e.g. `Depends(get_hierarchy_manager)`) if the endpoint needs chain system access.

## Step 3: Run Server and Quick Test

```bash
python -m hierachain.api.server
```

Open `http://localhost:2661/docs` to try on Swagger UI or use `curl`:

```bash
curl -s -X POST http://localhost:2661/api/ledger/ping \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

If API key authentication is enabled (production), add the header per `settings.API_KEY_NAME`:

```bash
-H 'X-API-Key: <your-key>'
```

## Step 4: Documentation Linking

* Update `docs/mkdocs.yml` to add this guide to the Guides section (if not already).
* Cross-link from API module/Reference page.

## Extension Notes

* Use clear path names, parameters, and response models.
* Handle errors with `HTTPException` (400/404/500) and transparent messages.
* Write tests (pytest) if the endpoint has important logic.

## Related

* API Module: [API](../modules/api.md)
* API Ledger Reference: [API Ledger](../reference/api-ledger.md)
* Config: [Config](../reference/config.md)
