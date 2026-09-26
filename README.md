# EVE Healthcare Diagnostic Booking API

FastAPI backend for diagnostic-centre discovery, test pricing, appointment booking, and simulated payments. The service uses PostgreSQL, asynchronous SQLAlchemy 2.x, Alembic migrations, Pydantic v2 validation, Argon2 password hashing, and JWT bearer authentication.

The client selects a diagnostic centre, test, and appointment time. The API verifies that the centre offers the test and copies the current centre-specific price into the booking. Users can only view or cancel their own bookings. Mock payment and webhook updates are atomic, and database uniqueness constraints protect against duplicate payments and repeated webhook events.

## Features

- Signup, login, password hashing, JWT authentication, and admin authorization.
- Public centre and diagnostic-test discovery.
- Admin-managed centres, tests, and centre-specific test prices.
- User-owned bookings with server-derived price and future appointment validation.
- Pending booking cancellation and mock successful/failed payments.
- Idempotent payment webhooks with event uniqueness, amount verification, and safe late-event behavior.
- Health and database-readiness endpoints.
- Swagger documentation with sample request and response values.

## Technology

- Python 3.11+
- FastAPI, Uvicorn, Pydantic v2, and pydantic-settings
- PostgreSQL, SQLAlchemy 2.x async, asyncpg, and Alembic
- PyJWT and pwdlib Argon2
- pytest, pytest-asyncio, and httpx
- Docker and Docker Compose

## Architecture

```text
Client
  |
  v
FastAPI
  +--> Authentication and authorization
  +--> Centre and diagnostic-test catalog
  +--> Booking service
  +--> Payment and webhook service
  |
  v
PostgreSQL
```

`app/api` contains routes and request dependencies, `app/services` contains business operations, `app/models` defines SQLAlchemy tables, `app/schemas` defines validated API contracts and OpenAPI examples, and `app/core` contains settings, security, and database setup. Production schema changes are applied by Alembic; the application does not call `Base.metadata.create_all()` at startup.

## Quick Start

### Local PostgreSQL

Create a PostgreSQL database, then configure a local `.env` file. Do not commit `.env`; it is ignored by Git.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` for your local database. `DATABASE_URL` must use the async driver URL form:

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/DATABASE_NAME
JWT_SECRET_KEY=replace-with-a-random-secret-at-least-32-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Apply migrations, then start the API:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Docker Compose

Docker Compose starts its own PostgreSQL 16 database and runs the migration before Uvicorn starts. Create `.env` for the app’s JWT settings, then run:

```powershell
Copy-Item .env.example .env
```

Replace the sample JWT key with a random value, then:

```powershell
docker compose up --build
```

The Compose app connects to its `db` service; its database is separate from any PostgreSQL instance configured for local Uvicorn. Compose exposes port 8000. Stop the stack with `Ctrl+C`; remove its persisted database volume only when you intentionally want to delete its data.

## Manual API Testing

Open `http://127.0.0.1:8000/docs` while Uvicorn is running. Every request and response schema has an example in Swagger. The generated OpenAPI document is at `http://127.0.0.1:8000/openapi.json`.

For endpoints requiring authentication, first call `POST /auth/signup`, then `POST /auth/login`. Copy the returned `access_token` into Swagger’s **Authorize** dialog as a bearer token. Signup creates a regular `USER`; the example administrator flow below is required before creating catalog data.

### 1. Register and log in

`POST /auth/signup`:

```json
{
  "email": "akash@example.com",
  "password": "StrongPassword123",
  "full_name": "Akash Kumar"
}
```

Passwords must contain 12 to 128 characters. The response contains the user ID, email, and name, never the password or password hash. `POST /auth/login` accepts JSON with `email` and `password`, and returns `access_token` plus `token_type: "bearer"`.

### 2. Promote an administrator

The service intentionally has no public endpoint for granting admin roles. Register the admin user first, then promote the trusted account through the database. For Docker Compose, open a PostgreSQL prompt:

```powershell
docker compose exec db psql -U postgres -d eve_healthcare
```

Run:

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'admin@example.com';
```

For local PostgreSQL, run the same SQL using your local `psql` connection. Log in with the promoted account and use its token for catalog administration.

### 3. Create the catalogue

With the admin bearer token, use `POST /centres/`:

```json
{
  "name": "Apollo Diagnostics",
  "location": "Delhi"
}
```

Then use `POST /tests/`:

```json
{
  "name": "CBC",
  "description": "Complete Blood Count"
}
```

Associate the returned centre and test IDs using `POST /centres/{centre_id}/tests/{test_id}`:

```json
{
  "price": 500.00
}
```

Use `GET /centres/{centre_id}/tests` to confirm the test and centre-specific price are available. Public discovery endpoints include `GET /centres/`, `GET /centres/{centre_id}`, `GET /tests/`, and `GET /tests/{test_id}`.

### 4. Create a booking and simulate payment

Log in as a normal user, authorize with that token, and call `POST /bookings/`:

```json
{
  "centre_id": 1,
  "test_id": 1,
  "appointment_at": "2026-10-01T10:30:00Z"
}
```

The client cannot provide `user_id`, `amount`, or `status`; unexpected fields are rejected. The server gets the user from the JWT, verifies the centre/test offering, and copies its database price. Appointment times without a timezone are interpreted as UTC; appointments must be in the future.

The response includes the centre and test names and starts with `status: "PENDING"`. To simulate payment for an owned booking, call `POST /payments/`:

```json
{
  "booking_id": 1,
  "simulate": "SUCCESS"
}
```

Use `"FAILED"` to simulate failure instead. The payment amount comes from the booking. The endpoint permits one payment per booking; payment success confirms the booking and payment failure marks it failed.

### 5. Test payment webhooks

Create a separate pending booking, then call `POST /payments/webhook/`:

```json
{
  "event_id": "evt_123456",
  "event_type": "payment.success",
  "provider_payment_id": "pay_123",
  "booking_id": 2,
  "amount": "500.00"
}
```

Supported event types are `payment.success` and `payment.failed`. Sending the same event ID again returns an idempotent response and does not create another payment. The amount must equal the booking amount. A distinct late event for a booking that already has a final status is recorded but cannot change that status or create another payment.

### Health Checks

- `GET /health` returns `{"status":"ok"}`.
- `GET /ready` runs a database connectivity check and returns `{"status":"ready"}` when PostgreSQL is reachable.

## API Reference

| Method | Endpoint | Access | Behavior |
| --- | --- | --- | --- |
| POST | `/auth/signup` | Public | Register a regular user |
| POST | `/auth/login` | Public | Validate credentials and issue a JWT |
| GET | `/centres/` | Public | List active centres |
| POST | `/centres/` | Admin | Create a centre |
| GET | `/centres/{centre_id}` | Public | Retrieve an active centre |
| GET | `/centres/{centre_id}/tests` | Public | List a centre’s active tests and prices |
| POST | `/centres/{centre_id}/tests/{test_id}` | Admin | Associate a test with a centre and price |
| GET | `/tests/` | Public | List active diagnostic tests |
| POST | `/tests/` | Admin | Create a diagnostic test |
| GET | `/tests/{test_id}` | Public | Retrieve an active diagnostic test |
| POST | `/bookings/` | User | Create a booking at the server-derived price |
| GET | `/bookings/` | User | List the caller’s bookings |
| GET | `/bookings/{booking_id}` | Owner | Retrieve an owned booking |
| POST | `/bookings/{booking_id}/cancel` | Owner | Cancel an owned pending booking |
| POST | `/payments/` | Owner | Simulate success or failure for an owned pending booking |
| POST | `/payments/webhook/` | Simulated provider | Process an idempotent payment event |
| GET | `/health` | Public | Liveness check |
| GET | `/ready` | Public | Database readiness check |

Errors use FastAPI’s standard `detail` response format. Validation failures return `422`; invalid credentials return `401`; non-admin writes return `403`; missing or non-owned bookings return `404`; duplicate or invalid state operations return `409`.

## Data Model

```text
User 1 ------ N Booking N ------ 1 Centre
                    |
                    +------------ 1 DiagnosticTest

Centre N ------ M DiagnosticTest
       through CentreTest(centre_id, test_id, price)

Booking 1 ------ 0..1 Payment

WebhookEvent(event_id UNIQUE)
```

`centre_tests` owns `price` because a diagnostic test can have a different price at each centre. Its `(centre_id, test_id)` composite primary key prevents duplicate offerings. A booking stores the selected centre, test, appointment, server-derived amount, and status. A unique payment `booking_id` enforces at most one payment per booking; `provider_payment_id` and webhook `event_id` are also unique.

## Authorization and State Transitions

- Signup always creates `USER`; only a trusted database administrator can promote a user to `ADMIN`.
- Admin role is checked from the user record for each protected catalog write.
- Booking create, list, detail, cancel, and mock-payment endpoints require bearer authentication. Detail and cancellation are owner-scoped; another user receives `404` to avoid revealing booking existence.
- Only pending bookings can be cancelled or receive a payment result.

```text
PENDING -- payment.success --> CONFIRMED
PENDING -- payment.failed  --> FAILED
PENDING -- owner cancel    --> CANCELLED
```

`CONFIRMED`, `FAILED`, and `CANCELLED` are terminal in this implementation. A payment/webhook operation that cannot be applied must not partially update the booking, payment, or webhook record.

Webhook processing inserts the globally unique event ID with `ON CONFLICT DO NOTHING`, locks the booking where supported, validates the amount, then writes payment and booking state in one transaction. Repeated IDs do not reapply changes. A different event arriving after the booking is final is marked processed without changing the booking or adding another payment.

## Migrations

Apply database changes with:

```powershell
python -m alembic upgrade head
```

Create a migration after editing SQLAlchemy models with:

```powershell
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
```

The initial revision creates the booking schema. The next revision aligns the unique email index with ORM metadata. In this workspace’s database, Alembic deliberately ignores a pre-existing unrelated `product` table so autogeneration will not propose dropping it; the table is not used or changed by this service.

## Tests

Run all tests with:

```powershell
python -m pytest -q
```

Tests create a temporary SQLite database and cover signup/login, admin access, catalogue operations, price-derived bookings, ownership, cancellation, payment results, duplicate payments, concurrent duplicate webhook delivery, webhook rollback on invalid bookings, amount mismatch, and late-event state protection. The integration suite does not modify the configured PostgreSQL database.

## Assumptions and Production Notes

- Payment is simulated; no real money is transferred.
- The assignment treats webhook requests as trusted simulated provider events. A production integration must verify a provider signature and should add rate limiting.
- Appointment availability, capacity, scheduling conflicts, rescheduling, refunds, and real payment-provider integration are outside scope.
- Webhook event IDs are globally unique; one payment is allowed for a booking.
- Log events avoid passwords, JWTs, and credential values.
- Configure a strong, unique `JWT_SECRET_KEY` through environment settings. Never commit `.env`.
