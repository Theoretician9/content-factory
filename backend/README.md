# Content Factory Backend

This is the backend service for the Content Factory SaaS platform. It consists of multiple microservices that handle different aspects of the platform's functionality.

## Architecture

The backend is built using a microservices architecture with the following components:

1. API Gateway - Entry point for all API requests
2. User Service - User management and authentication
3. Billing Service - Subscription and payment management
4. Admin Service - Administrative functions and monitoring
5. Scenario Service - Workflow and automation management
6. Content Service - Content generation and management
7. Invite Service - Invitation and messaging management
8. Parsing Service - Data collection and processing
9. Integration Service - Third-party integrations
10. Task Worker - Background task processing

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- MySQL 8.0
- Redis 7.0

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd backend
```

2. Create and configure the environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Build and start the services:
```bash
docker-compose up -d
```

4. Initialize the database:
```bash
# For User Service
cd user-service
alembic upgrade head
```

## Development

### Local Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the service:
```bash
uvicorn main:app --reload
```

### API Documentation

Once the services are running, you can access the API documentation at:
- API Gateway: http://localhost:8000/docs
- User Service: http://localhost:8001/docs
- Other services: http://localhost:800X/docs (where X is the service port)

## Testing

Run tests using pytest:
```bash
pytest
```

## Deployment

1. Build the Docker images:
```bash
docker-compose build
```

2. Push the images to your registry:
```bash
docker-compose push
```

3. Deploy to your server:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Security

- All services use HTTPS
- JWT authentication for API access
- Role-based access control (RBAC)
- Rate limiting on all endpoints
- Input validation using Pydantic
- Secure password hashing with bcrypt

## Monitoring

- Health check endpoints available at `/health` for each service
- Prometheus metrics available at `/metrics`
- Logging to stdout/stderr for container orchestration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 