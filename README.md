# Document Similarity Detection System

A high-performance plagiarism and near-duplicate detection engine using Locality-Sensitive Hashing (LSH) and MinHash.

## Overview
Comparing every document in a large corpus against every other document requires $O(N^2)$ comparisons, which quickly becomes unscalable. This project solves that problem by implementing the **MinHash** algorithm to create fixed-length signatures of documents, and **Locality-Sensitive Hashing (LSH)** to group similar documents into buckets. Instead of an $O(N^2)$ search, the system only performs exact comparisons on documents that share an LSH bucket—reducing comparison space by up to 99% while maintaining high accuracy.

## Tech Stack
*   **Backend:** Python, FastAPI, Pydantic
*   **Storage (Primary):** PostgreSQL (asyncpg), raw SQL (no ORM)
*   **Storage (LSH Index):** Redis (Optimized for $O(1)$ set unions)
*   **Frontend:** React 19, Vite, Tailwind CSS, Lucide Icons
*   **Algorithms:** K-Shingling, MinHash, LSH (Implemented from scratch)

## Key Features
*   **Algorithmic Transparency:** Custom-built MinHash and LSH algorithms without relying on black-box similarity libraries.
*   **O(1) Candidate Lookups:** Uses Redis `Sets` to handle LSH bucket grouping, resulting in blazing-fast candidate generation.
*   **Dual Storage Engine:** Separates persistent, structured data (Postgres) from ephemeral, high-throughput candidate sets (Redis).
*   **Interactive Dashboard:** React frontend to upload documents, visualize corpus statistics, and compare benchmark speeds between Naive ($O(N^2)$) and LSH ($O(N)$) lookup engines.
*   **Side-by-Side Comparison:** View exact matching segments (shared shingles) between flagged duplicate pairs.

## Project Structure
```text
.
├── backend/
│   ├── app/
│   │   ├── algorithms/    # Core logic: shingling, minhash, lsh
│   │   ├── api/           # FastAPI routers (documents, analysis)
│   │   ├── core/          # Configs, Redis client, Custom exceptions
│   │   ├── db/            # Postgres connection pooling and raw SQL queries
│   │   └── services/      # Business logic bridging algorithms and DBs
│   ├── tests/             # Pytest suite for API and Algorithms
│   ├── scripts/           # DB initialization and benchmarking scripts
│   └── main.py            # FastAPI entry point
├── frontend/
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   └── pages/         # Dashboard, Results, and PairDetail views
│   └── index.html         # React entry point
├── schema.sql             # PostgreSQL schema definition
├── docker-compose.yml     # Infrastructure services configuration
└── Makefile               # CLI shortcuts for starting services
```

## Setup Instructions

### Prerequisites
*   Python 3.11+
*   Node.js 18+
*   Docker & Docker Compose (or Podman)

### 1. Start Infrastructure (Postgres & Redis)
Use the included Makefile to spin up the database containers:
```bash
make services-up
```

### 2. Backend Setup
Navigate to the `backend` directory, create a virtual environment, and install dependencies:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create an `.env` file from the example:
```bash
cp .env.example .env
```

Initialize the database schema:
```bash
python scripts/init_db.py
```

Start the FastAPI backend:
```bash
make dev
# The API will run on http://localhost:8000
```

### 3. Frontend Setup
Open a new terminal, navigate to the `frontend` directory, and install dependencies:
```bash
cd frontend
npm install
```

Start the Vite development server:
```bash
npm run dev
# The frontend will run on http://localhost:5173
```

### 4. Running Tests
To run the automated backend test suite (API and Algorithms):
```bash
cd backend
source .venv/bin/activate
pytest tests/
```
