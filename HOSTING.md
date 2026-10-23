# Putting the app online (Streamlit Community Cloud)

## What was wrong
The PostgreSQL you installed runs on **your computer**. The online app runs on Streamlit's servers, where there is no
PostgreSQL at `localhost`, and your `.env` is (correctly) not uploaded. So the Admin tab could not connect.
The Predict and Model tabs never needed the database.

## What the app does now
The Admin tab picks what to use automatically:

| Situation | What you get |
|---|---|
| PostgreSQL works (your PC, or `DATABASE_URL` set) | Full Admin tab: login from the `app_users` table, data table, CSV download, user management |
| No PostgreSQL, no `DATABASE_URL` (the default online) | **Demo mode**: read-only copy of the data from `artifacts/waste_bin.db`, one admin login from Secrets, no user management |
| `DATABASE_URL` set but not working | A short, safe error message (no server names). Predict and Model tabs still work |

Predictions use the coefficients saved in `artifacts/metrics.json`, so the online app no longer needs scikit-learn
or the `.pkl` file. It only needs `pandas`, `streamlit` and `psycopg`.

## Option A: demo mode online (no extra service, works today)
1. Push the updated files to GitHub (commands below).
2. In Streamlit Community Cloud open your app > **Manage app** > **Settings** > **Secrets** and paste:

       APP_ADMIN_USER = "admin"
       APP_ADMIN_PASSWORD = "choose-a-strong-password"

3. Save. The app restarts. Open the Admin tab: you see the blue "Demo mode" note and the login form.

## Option B: full PostgreSQL online
1. Create a cloud PostgreSQL database (for example Neon or Supabase) and copy its connection string:

       postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require

2. On your PC add to `.env`, then run `python setup_db.py` (it creates the tables, loads the data, creates your admin):

       DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
       APP_ADMIN_USER=admin
       APP_ADMIN_PASSWORD=choose-a-strong-password

   Put a `#` in front of the `DATABASE_URL` line to go back to your local PostgreSQL.
3. In the app's **Secrets** paste only:

       DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"

## Pushing the update to GitHub
From the project folder:

    git add app.py db.py setup_db.py requirements.txt requirements-dev.txt HOSTING.md README.md DATABASE_SETUP.md
    git status
    git commit -m "Hosted-friendly Admin tab and slim requirements"
    git push

Check that `git status` does NOT list `.env`. Streamlit redeploys on every push. If it does not,
use **Manage app** > the three-dot menu > **Reboot app**.

## Files
- `requirements.txt`: what the **online** app installs (pandas, streamlit, psycopg). Kept small on purpose.
- `requirements-dev.txt`: for your PC (adds scikit-learn, matplotlib, jupyter). Use `pip install -r requirements-dev.txt`.

## Security notes
- The app is public: use strong, unique passwords, and not the short ones used for testing.
- If a password or connection string appeared in a chat or screenshot, change it.
- The 5-attempt lockout works per browser session only; it slows guessing, it does not stop a determined attacker.
- Secrets are only stored in Streamlit's Settings. Never commit them.

## Troubleshooting
- **"Admin login is not set up":** add `APP_ADMIN_USER` and `APP_ADMIN_PASSWORD` to Secrets (Option A).
- **"the database refused the user name or password":** copy the connection string again.
- **"requires SSL":** the URL must end with `?sslmode=require`.
- **ModuleNotFoundError: psycopg:** `requirements.txt` in the repo root must contain `psycopg[binary]`.
- **Logs:** Manage app > Logs shows the full technical error (visitors never see it).
