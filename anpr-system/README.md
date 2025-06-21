# City-wide ANPR System

## Overview
This repository contains a production-grade, GPU-accelerated, city-wide Automatic Number Plate Recognition (ANPR) system designed for on-prem or cloud deployment. The system is modular, secure, scalable, and capable of 24×7 operation across 100+ HD CCTV streams.

## Repository Structure
```
anpr-system/
├── ingestion_service/      # Frame capture & batching
├── detection_service/      # YOLOv8 vehicle & plate bbox detection
├── ocr_service/            # Plate image preprocessing & OCR
├── tracking_service/       # DeepSORT/ByteTrack identity tracking
├── storage_service/        # Metadata DB + encrypted S3 storage
├── api_service/            # FastAPI REST + JWT auth + license checks
├── dashboard/              # React/TypeScript + Tailwind CSS + Leaflet map UI
├── license_server/         # (optional) remote license validation stub
├── notebooks/              # Training / fine-tuning YOLOv8 notebooks
├── infra/                  # Docker Compose, Kubernetes manifests, Helm charts
├── .github/                # GitHub Actions CI workflows
├── docs/                   # Architecture diagrams, setup guides
├── scripts/                # CLI tools (e.g., license-generate)
└── README.md
```

## Prerequisites
- Docker & Docker Compose
- NVIDIA Container Toolkit for GPU support
- Python 3.10+
- Node.js 16+
- Access to RTSP/HLS camera streams
- PostgreSQL with PostGIS extension
- MinIO or AWS S3 for blob storage

## Getting Started

### Environment Setup
- Copy `.env.example` to `.env` and configure your environment variables (RTSP URLs, DB credentials, license paths, etc.)

### Running Locally
```bash
cd infra
docker-compose up --build
```

### Access Points
- API Service: http://localhost:8000
- Dashboard: http://localhost:3000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Development
- Each microservice lives in its own folder with a dedicated Dockerfile.
- Use GPU-enabled containers for detection and training services.
- Use FastAPI for backend services and React + Tailwind CSS for the dashboard.

## CI/CD
- GitHub Actions workflows lint, test, build, and push Docker images.
- Integration and load tests included.

## Documentation
- See `docs/` for architecture diagrams, API schema, and troubleshooting guides.

## License
- License enforcement is implemented via JWT and license keys.
- Use `scripts/license-generate` to create signed license files.

---

Please refer to the `docs/` folder for detailed setup and architecture information.
