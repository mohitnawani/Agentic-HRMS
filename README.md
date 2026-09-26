# Agentic HRMS

Full-stack HRMS with a React/Vite frontend, FastAPI backend, PostgreSQL/pgvector,
and a Gemini-powered HR assistant.

## Deploy to Render

The repository includes a `render.yaml` Blueprint that creates:

- a React static site;
- a Docker-based FastAPI web service; and
- a PostgreSQL database with pgvector enabled by the first migration.

Automatic deploys are disabled. Deployments remain manual and no CI/CD pipeline
is required.

### First deployment

1. Push this repository and branch to GitHub.
2. In Render, choose **New > Blueprint** and connect the repository.
3. Render reads `render.yaml`. Enter the prompted secret values:
   - `BOOTSTRAP_ADMIN_EMAIL`: the first administrator's valid email address.
   - `BOOTSTRAP_ADMIN_PASSWORD`: at least 12 characters and no more than 72 bytes.
   - `GEMINI_API_KEY`: required for embeddings, policy RAG, and assistant features.
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and
     `CLOUDINARY_API_SECRET`: required for persistent policy documents and photos.
4. Apply the Blueprint and wait for the database, API, and frontend to finish.
5. Open the frontend URL and sign in using the bootstrap administrator account.

### Demo accounts (seeded when `SEED_DEMO_DATA=true`)

Every fresh deploy also seeds a demo team so dashboards, approvals, and chat
have content immediately. All demo accounts use the password `DemoPass123!`:

| Email | Role | Name |
| --- | --- | --- |
| `admin.demo@company.com` | Admin | Vikram Malhotra |
| `hr.demo@company.com` | HR | Priya Nair |
| `rahul.verma@company.com` | Employee | Rahul Verma |
| `amit.patel@company.com` | Employee | Amit Patel |
| `vaishali.gupta@company.com` | Employee | Vaishali Gupta |
| `sneha.reddy@company.com` | Employee | Sneha Reddy |
| `arjun.mehta@company.com` | Employee | Arjun Mehta |
| `kavya.iyer@company.com` | Employee | Kavya Iyer |

Seeding is idempotent — re-running bootstrap never duplicates rows. To disable
it, set `SEED_DEMO_DATA=false` on the API service and redeploy the API.

The backend start script applies all Alembic migrations and safely bootstraps
reference data on every start. It creates the administrator only when the email
does not already exist; it never resets an existing password.

### Manual updates

Because `autoDeployTrigger` is set to `off`, pushing code does not deploy it.
Open each Render service and choose **Manual Deploy > Deploy latest commit**.
Deploy the API first when a change includes a database migration, then deploy the
static frontend.

### Local development

Copy `.env.example` to `.env` and `frontend/.env.example` to `frontend/.env`, then
fill in your local secret values. The defaults use the local API at
`http://127.0.0.1:8000/api/v1`.

Google login is hidden by default. To enable it later, set
`VITE_GOOGLE_LOGIN_ENABLED=true`, supply `VITE_GOOGLE_CLIENT_ID`, configure the
same client ID in the backend, and add the deployed frontend origin in Google
Cloud Console.

> **Demo hosting note:** the Blueprint uses Render's free plans. Free web
> services can sleep when idle, and a free Render Postgres database expires
> after 30 days and has no backups. Upgrade the database before using this for
> long-lived or production HR data.
