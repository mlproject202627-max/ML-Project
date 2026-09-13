# Sentinel Backend

Insider Threat Detection / UEBA Platform Backend

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.x
- **Validation**: Pydantic v2
- **Auth**: JWT-based authentication
- **Migrations**: Alembic

## Quick Start

### 1. Using Docker (Recommended)

```bash
docker compose up --build
```

This starts:
- Backend API at `http://localhost:8000`
- PostgreSQL at `http://localhost:5432`

### 2. Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Seed the database
python -m app.utils.seed

# Start the server
uvicorn app.main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@sentinel.demo | Admin123! |
| Analyst | sarah.chen@sentinel.demo | Analyst123! |
| Manager | james.wilson@sentinel.demo | Manager123! |
| Viewer | viewer@sentinel.demo | Viewer123! |

**⚠️ These are DEMO credentials for development only.**

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/logout` - Logout
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get current user

### Dashboard
- `GET /api/v1/dashboard` - Get dashboard metrics

### Users
- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user

### Anomalies
- `GET /api/v1/anomalies` - List anomalies
- `GET /api/v1/anomalies/{id}` - Get anomaly
- `PATCH /api/v1/anomalies/{id}` - Update anomaly

### Investigations
- `GET /api/v1/investigations` - List investigations
- `GET /api/v1/investigations/{id}` - Get investigation
- `POST /api/v1/investigations` - Create investigation
- `PATCH /api/v1/investigations/{id}` - Update investigation
- `POST /api/v1/investigations/{id}/assign` - Assign investigation
- `POST /api/v1/investigations/{id}/resolve` - Resolve investigation

### Activity
- `GET /api/v1/activity` - List activities

### Policies
- `GET /api/v1/policies` - List policies
- `POST /api/v1/policies` - Create policy
- `PUT /api/v1/policies/{id}` - Update policy
- `DELETE /api/v1/policies/{id}` - Delete policy
- `PATCH /api/v1/policies/{id}/status` - Toggle policy

### Notifications
- `GET /api/v1/notifications` - List notifications
- `PATCH /api/v1/notifications/{id}/read` - Mark as read
- `PATCH /api/v1/notifications/read-all` - Mark all as read

### Ingestion
- `POST /api/v1/ingestion/activities` - Ingest activities
- `POST /api/v1/ingestion/csv` - Import CSV

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── core/                 # Configuration, security, database
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── api/                  # Route handlers
│   ├── services/             # Business logic
│   ├── ml/                   # ML adapter interface
│   └── utils/                # Utilities, seed script
├── alembic/                  # Database migrations
├── tests/                    # Test suite
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Environment Variables

See `.env.example` for all configuration options.

## Security Features

- JWT-based authentication
- Role-based access control (RBAC)
- Password hashing with bcrypt
- CORS protection
- Security headers
- Rate limiting ready
- IDOR protection
- Audit logging

## ML Integration

The backend includes a mock ML adapter interface. To integrate a real model:

1. Implement the `AnomalyDetector` interface in `app/ml/interface.py`
2. Replace the `MockAnomalyDetector` in `app/ml/adapter.py`
3. The API will work without changes

## License

Demo project for educational purposes.
