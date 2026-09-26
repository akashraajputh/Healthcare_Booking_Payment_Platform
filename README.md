# EVE Healthcare Diagnostic Booking API

A focused backend for diagnostic-centre discovery, test pricing, appointment booking, and simulated payment processing. FastAPI exposes typed request/response contracts and OpenAPI documentation; PostgreSQL stores the domain model with Alembic-managed schema changes. Booking prices are always read from the centre-test offering, and payment changes are committed atomically with booking state.

The API is intentionally small enough to follow in an interview while protecting the important boundaries: authenticated booking, admin-managed catalog data, per-user booking visibility, explicit state transitions, database uniqueness for payments and webhook event IDs, and rollback on invalid provider events.

## Technology

- Python 3.11+
- FastAPI and Pydantic v2 / pydantic-settings
- PostgreSQL, SQLAlchemy 2.x async, and asyncpg
- Alembic migrations
- PyJWT and pwdlib Argon2 password hashing
- pytest, pytest-asyncio, and httpx
- Docker Compose and Uvicorn

## Architecture

```text
Client
  |
  v
FastAPI
  +--> Authentication and authorization
  +--> Centre and test catalog
  +--> Booking service
  +--> Payment and webhook service
  |
  v
PostgreSQL
```

The application is organized into `app/api` for HTTP and dependencies, `app/services` for business operations, `app/models` for SQLAlchemy entities, `app/schemas` for API contracts, and `app/core` for configuration, security, and database setup. Production schema setup uses Alembic; the app does not call `Base.metadata.create_all()` at startup.

## Setup

### Docker

Copy `.env.example` to `.env`, replace `JWT_SECRET_KEY` with a random secret of at least 32 characters, then run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose waits for PostgreSQL, applies `alembic upgrade head`, and starts Uvicorn on port 8000. The API docs are at `http://localhost:8000/docs`; the OpenAPI document is at `http://localhost:8000/openapi.json`.

### Local

Create and activate a virtual environment, then install dependencies:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `DATABASE_URL` for a local PostgreSQL instance and set a unique `JWT_SECRET_KEY`. Create the development database, then run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Generate a future migration after model changes with:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Run the test suite with `pytest`. Tests use a temporary SQLite database and do not require a running PostgreSQL server.

## Administrator Setup

Signup always creates a `USER`; clients cannot choose their role. Promote a trusted account using a controlled database session after registering it:

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'admin@example.com';
```

Then log in again to receive a token and use it for centre, test, and centre-test administration. Do not expose this SQL operation through a public endpoint.

## API Endpoints

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/auth/signup` | No | Register a user |
| POST | `/auth/login` | No | Issue a bearer JWT |
| GET | `/centres/` | No | List active centres |
| GET | `/centres/{centre_id}` | No | Get an active centre |
| POST | `/centres/` | Admin | Create a centre |
| GET | `/centres/{centre_id}/tests` | No | List tests and prices offered by a centre |
| POST | `/centres/{centre_id}/tests/{test_id}` | Admin | Associate a test with a centre and price it |
| GET | `/tests/` | No | List active diagnostic tests |
| GET | `/tests/{test_id}` | No | Get an active diagnostic test |
| POST | `/tests/` | Admin | Create a diagnostic test |
| POST | `/bookings/` | Yes | Book an offered test at its current centre price |
| GET | `/bookings/` | Yes | List the caller's bookings |
| GET | `/bookings/{booking_id}` | Yes | Get an owned booking |
| POST | `/bookings/{booking_id}/cancel` | Yes | Cancel an owned pending booking |
| POST | `/payments/` | Yes | Simulate payment success or failure for an owned booking |
| POST | `/payments/webhook/` | Provider | Process simulated provider event idempotently |
| GET | `/health` | No | Liveness response |
| GET | `/ready` | No | Check database connectivity |

### Example Requests

Signup:

```json
{
  "email": "akash@example.com",
  "password": "StrongPassword123",
  "full_name": "Akash Kumar"
}
```

Create a booking with a bearer token. Extra fields such as `amount`, `user_id`, and `status` are rejected; appointment timestamps without an offset are interpreted as UTC.

```json
{
  "centre_id": 1,
  "test_id": 2,
  "appointment_at": "2026-10-01T10:30:00"
}
```

The response contains the server-derived amount and joined centre/test names:

```json
{
  "id": 101,
  "centre_id": 1,
  "centre_name": "EVE Central Lab",
  "test_id": 2,
  "test_name": "CBC",
  "appointment_at": "2026-10-01T10:30:00Z",
  "amount": "500.00",
  "status": "PENDING",
  "created_at": "2026-09-26T12:00:00Z"
}
```

Mock payment request:

```json
{
  "booking_id": 101,
  "simulate": "SUCCESS"
}
```

Webhook request:

```json
{
  "event_id": "evt_123456",
  "event_type": "payment.success",
  "provider_payment_id": "pay_123",
  "booking_id": 101,
  "amount": "500.00"
}
```

## Data Model

- A user has many bookings; each booking belongs to one user, centre, and diagnostic test.
- Centres and diagnostic tests are many-to-many through `centre_tests`.
- `centre_tests.price` is the price for that specific centre/test pair. Price is not a property of the test because different centres may charge differently.
- A booking has at most one payment. Provider payment IDs and webhook event IDs are unique in the database.
- Webhook events are recorded with processing status and timestamps.

The composite primary key on `(centre_id, test_id)` prevents duplicate offerings. The unique payment-per-booking and webhook-event constraints are final database-level defenses against concurrent duplicate processing.

## Authorization and State Rules

- Only admins can create centres, tests, or centre-test prices. New signups cannot assign themselves an admin role.
- Booking creation requires a bearer token and an active centre/test offering. The amount is copied from the offering at booking time.
- Booking reads and cancellation are owner-scoped. Other users receive `404` so booking existence is not disclosed.
- Only `PENDING` bookings can be cancelled or receive a new payment outcome.
- Payment success moves a pending booking to `CONFIRMED`; failure moves it to `FAILED`. These states are terminal in this scope.
- The first valid webhook event for a pending booking determines its payment result. A later distinct event for an already-final booking is recorded as processed but cannot overwrite booking state or create a second payment.
- Repeated event IDs return an idempotent success response without applying payment changes. Amount mismatches and unknown bookings are rejected, and the event insert rolls back with the transaction.
- Mock payment operations lock the booking where supported and atomically write payment plus booking status. Webhook event insertion uses `ON CONFLICT DO NOTHING` on its unique event ID before applying changes, serializing duplicate event processing in PostgreSQL.

## Assumptions and Production Notes

- Payment is simulated; no money moves and provider events are assumed trusted for this assignment.
- A real deployment must authenticate webhook requests (for example, verify a provider signature) and apply rate limits; the public simulation endpoint intentionally has no provider-secret scheme.
- Appointment availability, capacity, rescheduling, refunds, and calendar conflict prevention are outside scope.
- Webhook event IDs are globally unique, and one payment is allowed per booking.
- Times without a timezone are treated as UTC; production clients should send explicit offsets.
- Structured operation logs avoid passwords and JWTs. Login failures are logged without email or credential values.
