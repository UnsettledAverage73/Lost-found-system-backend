# 🚀 Lost & Found System - Backend

Welcome to the heart of the Lost & Found System! This FastAPI application powers all the core functionalities, from user authentication to report management and real-time updates.

## 🌟 Features

-   **🔐 User Authentication:** Secure registration, login, and user profile management.
-   **📝 Report Management:** Create, retrieve, and manage both lost and found reports for items and people.
-   **☁️ Image Storage:** Seamlessly store and retrieve report-related images using Supabase Storage.
-   **⚡ Real-time Updates:** Stay informed with live updates via WebSockets for critical events.
-   **🔍 Matching System (WIP):** An intelligent system to match lost items/people with found ones (AI/ML integration planned).
-   **📷 QR Code Generation (WIP):** Placeholder for future QR code functionalities.

## 🛠️ Setup

### Prerequisites

Before you begin, ensure you have the following installed:

-   **Python 3.9+**
-   **`pip`** (Python package installer)
-   **`venv`** (Python virtual environment)
-   **Supabase Account:** A free account with a new project created and its URL and Anon Key handy.

### Environment Variables

Create a `.env` file in the `backend/` directory with the following variables. **Replace the placeholder values with your actual Supabase credentials.**

```dotenv
SUPABASE_URL="YOUR_SUPABASE_PROJECT_URL"
SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
SUPABASE_REPORT_PHOTOS_BUCKET="report_photos" # This bucket must be created in Supabase Storage
```

**⚠️ Important:** You *must* create the `report_photos` bucket in your Supabase Storage.
Navigate to your Supabase project dashboard -> **Storage** -> Click **"New bucket"** and name it `report_photos`. Ensure its public access settings are configured as per your requirements.

### Supabase Database Setup

For user profile management, you'll need a `profiles` table in your Supabase database. Copy and paste the following SQL commands into your Supabase SQL Editor and run them:

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

Follow these steps to set up your backend:

1.  **Navigate to the `backend` directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Running the Application

To start the FastAPI server, navigate to the **root of your project** (`Lost-Found-System/`) and execute the following commands:

```bash
# If you are currently in the backend directory, go up one level
cd ..

# Activate the virtual environment
source backend/venv/bin/activate

# Run the FastAPI application with auto-reloading
uvicorn backend.api.main:app --reload
```

The backend API will now be accessible at `http://localhost:8000`.

## 🗺️ API Endpoints

Here's a quick overview of the key API endpoints:

### Authentication
-   `POST /auth/register`: Register a new user with contact, password, role, and consent.
-   `POST /auth/token`: Log in a user and obtain an access token.
-   `GET /auth/me`: Retrieve details of the currently authenticated user.

### Reports
-   `POST /reports/lost`: Submit a new lost report with details and optional photos.
-   `POST /reports/found`: Submit a new found report with details, optional audio transcription, and photos.
-   `GET /reports`: Fetch a list of all reports, with options to filter by type (lost/found) and status.
-   `GET /reports/{report_id}`: Retrieve detailed information for a specific report.

### Matches
-   `GET /matches/report/{report_id}`: Find potential matches for a given report.
-   `POST /matches/{match_id}/status`: Update the status of a specific match (e.g., "PENDING", "CONFIRMED", "REJECTED").

### Users
-   `GET /users/me`: Get the profile information of the authenticated user.
-   `PUT /users/me`: Update the profile information of the authenticated user.

### WebSockets
-   `ws /ws/{user_id}`: Establish a WebSocket connection for real-time updates and notifications.

## 🐘 Database (Supabase)

This project leverages [Supabase](https://supabase.com/) as its backend-as-a-service, utilizing PostgreSQL for database management and Supabase Storage for handling file uploads. Ensure your Supabase project is correctly configured as per the `Environment Variables` and `Supabase Database Setup` sections.

## 🤝 Running Both Frontend and Backend (Monorepo Setup)

If you prefer to manage both the frontend and backend from the root directory of the `Lost-Found-System` project, here's how you can do it:

1.  **Open two separate terminal windows.**

2.  **In the first terminal (for Backend):**
    -   Navigate to the project root:
        ```bash
        cd /path/to/Lost-Found-System
        ```
    -   Activate the backend virtual environment and start the FastAPI server:
        ```bash
        source backend/venv/bin/activate && uvicorn backend.api.main:app --reload
        ```

3.  **In the second terminal (for Frontend):**
    -   Navigate to the frontend directory:
        ```bash
        cd /path/to/Lost-Found-System/frontend
        ```
    -   Start the Next.js development server:
        ```bash
        npm run dev
        ```

This setup allows you to see backend logs and frontend output simultaneously, which is great for development and debugging.
