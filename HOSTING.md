# Hosting the app online (Streamlit Community Cloud + cloud PostgreSQL)

## Why the Admin tab shows "PostgreSQL is not reachable" online
The PostgreSQL you installed runs **on your own computer** (`localhost`). A hosted app runs on Streamlit's servers,
where there is no PostgreSQL at `localhost`, and your `.env` file is not uploaded (it is in `.gitignore`).
The Predict and Model tabs work online, because they only need the files in `artifacts/`.
To make the Admin tab work online you need a database that is reachable from the internet.

## Step 1. Create a cloud PostgreSQL database
Use a hosted PostgreSQL service (for example Neon or Supabase; check each one's current free-plan limits).
Create a project and copy its **connection string**. It looks like:

    postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require

Keep it secret. Anyone who has it can read and change your data.

## Step 2. Load your data into it (from your PC)
Add to your local `.env` (keep the other lines, or leave them unused):

    DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
    APP_ADMIN_USER=admin
    APP_ADMIN_PASSWORD=choose-a-STRONG-password

Then run, in the activated environment:

    python setup_db.py

It creates the tables, loads the 14,295 rows, and creates your admin login in the cloud database.
(To use your local PostgreSQL again, put `#` in front of the `DATABASE_URL` line.)

## Step 3. Give the hosted app the same settings
In Streamlit Community Cloud: open your app > **Manage app** > **Settings** > **Secrets**, and paste:

    DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"

Save. The app restarts and the Admin tab should show the login form.
Never put the connection string in GitHub.

## Step 4. Check the repository
The GitHub repo that Streamlit deploys must contain `app.py`, `db.py`, `requirements.txt` (with `psycopg[binary]`)
and the `artifacts/` folder (`bin_model.pkl`, `metrics.json`, the PNG files). It must NOT contain `.env`.
Replace `db.py` and `setup_db.py` with the new versions, then commit and push. Streamlit redeploys automatically.

## Security notes (the app is public now)
- Use strong, unique passwords for the cloud database and for `APP_ADMIN_PASSWORD`. Do not reuse the short ones from testing.
- In hosted mode the app uses the one database user your provider gave you, so there is no separate read-only role.
  The app code only reads readings and adds users, but protect the connection string.
- The login lockout (5 tries) works per browser session only. It slows guessing but does not stop a determined attacker.
- If you shared any password or connection string in a chat or a screenshot, change it.

## Troubleshooting
- **SSL error / "connection requires SSL":** make sure the URL ends with `?sslmode=require`.
- **password authentication failed:** copy the connection string again from the provider.
- **ModuleNotFoundError: psycopg:** `requirements.txt` in the repo root must include `psycopg[binary]`.
- **scikit-learn version warning online:** pin the version you use locally in `requirements.txt`
  (see it with `pip show scikit-learn`, then add a line such as `scikit-learn==1.9.1`).
- **First load is slow:** some free plans pause idle databases and need a few seconds to wake.
