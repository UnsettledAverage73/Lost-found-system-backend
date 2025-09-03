# Backend

This directory contains the FastAPI backend application for the Lost & Found System.

## Table of Contents
- [Features](#features)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Installation](#installation)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Database (Supabase)](#database-supabase)

## Features
- User Authentication (Registration, Login, User Profile)
- Report Management (Lost and Found items/people)
- Image Storage (via Supabase Storage)
- Real-time Updates (via WebSockets)
- Matching System (placeholder for AI/ML features)
- QR Code generation (placeholder)

## Setup

### Prerequisites
- Python 3.9+
- `pip` (Python package installer)
- `venv` (Python virtual environment)
- Supabase Account (with a project created)

### Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

```
SUPABASE_URL="YOUR_SUPABASE_PROJECT_URL"
SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
SUPABASE_REPORT_PHOTOS_BUCKET="report_photos" # This bucket must be created in Supabase Storage
```

**Important:** Ensure you have created the `report_photos` bucket in your Supabase Storage. Go to your Supabase project dashboard -> Storage -> New bucket.

### Supabase Database Setup

You need a `profiles` table in your Supabase database for user management. Run the following SQL in your Supabase SQL Editor:

```sql
CREATE TABLE public.profiles (
    id uuid references auth.users not null primary key,
    role text default 'VOLUNTEER'::text not null,
    contact text not null,
    consent_face_qr boolean default false not null,
    created_at timestamp with time zone default now() not null
);

alter table public.profiles enable row level security;

create policy "Public profiles are viewable by everyone."
  on public.profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on public.profiles for insert
  with check ( auth.uid() = id );

create policy "Users can update their own profile."
  on public.profiles for update
  using ( auth.uid() = id );
```

### Installation

1.  **Navigate to the `backend` directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

To run the FastAPI server, navigate to the **root of the project** (`Lost-Found-System/`) and execute:

```bash
cd .. # If you are currently in the backend directory
source backend/venv/bin/activate
uvicorn backend.api.main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Endpoints

-   **Authentication:**
    -   `POST /auth/register`: Register a new user.
    -   `POST /auth/token`: Login and get an access token.
    -   `GET /auth/me`: Get current user details (requires authentication).

-   **Reports:**
    -   `POST /reports/lost`: Create a new lost report (requires authentication).
    -   `POST /reports/found`: Create a new found report (requires authentication).
    -   `GET /reports`: List all reports, with optional type and status filters.
    -   `GET /reports/{report_id}`: Get details of a specific report.

-   **Matches:**
    -   `GET /matches/report/{report_id}`: Get matches for a specific report.
    -   `POST /matches/{match_id}/status`: Update the status of a match.

-   **Users:**
    -   `GET /users/me`: Get current user profile.
    -   `PUT /users/me`: Update current user profile.

-   **WebSockets:**
    -   `ws /ws/{user_id}`: WebSocket endpoint for real-time updates.

## Database (Supabase)

This backend uses Supabase for database management (PostgreSQL) and file storage (Supabase Storage). Ensure your Supabase project is set up correctly with the necessary tables and buckets.
