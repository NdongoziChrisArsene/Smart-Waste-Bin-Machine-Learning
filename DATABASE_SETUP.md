# PostgreSQL setup (Windows / PowerShell)

## 1. Install PostgreSQL (skip if already installed)
Download the Windows installer from postgresql.org/download/windows. During the install:
- choose a password for the `postgres` superuser and **remember it**,
- keep port **5432**, and keep pgAdmin 4 ticked.

Check that the server is running:

    Get-Service *postgres*

If the status is `Stopped`, start it with `Start-Service <name shown>` (open PowerShell as administrator).

## 2. Add the new files to your project folder
Copy `db.py`, `setup_db.py`, `app.py` (replace the old one), `requirements.txt`, `.env.example` and `.gitignore`
into the same folder as your notebook. Then, in your activated environment:

    pip install -r requirements-dev.txt

## 3. Create your .env
    Copy-Item .env.example .env
    notepad .env

Fill in: `PG_SUPERPASS` (the postgres password from step 1), `DB_ADMIN_PASSWORD`, `DB_APP_PASSWORD`,
`APP_ADMIN_PASSWORD` (8+ characters), and change `APP_ADMIN_USER` if you like. Use different passwords for each.
`.env` is in `.gitignore`, so it will not be pushed to GitHub.

## 4. Make sure the notebook was run
`artifacts\waste_bin.db` must exist (it is created by the notebook).

## 5. Run the setup (once)
    python setup_db.py

It creates the roles `waste_admin` and `waste_app`, the database `waste_bin`, the tables `waste_readings` and
`app_users`, the permissions, loads the cleaned data, and creates your first app admin user.
It is safe to run again. After re-running the notebook, refresh the data with `python setup_db.py --reload`.

## 6. Start the app
    streamlit run app.py

Open the **Admin** tab and log in with `APP_ADMIN_USER` / `APP_ADMIN_PASSWORD`.
- **admin** users see the data, can download it, and can create other users.
- **viewer** users only see and download the data.

## 7. Open the database directly
**pgAdmin 4:** right-click Servers > Register > Server. Host `localhost`, port `5432`, database `waste_bin`,
username `waste_admin`, password = your `DB_ADMIN_PASSWORD`.

**psql** (change the version folder to yours):

    & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U waste_admin -d waste_bin -h localhost

Then try: `SELECT * FROM waste_readings LIMIT 10;` and `SELECT username, role FROM app_users;`

## Who can do what
| Account | Type | Can do |
|---|---|---|
| `postgres` | PostgreSQL superuser | Everything. Used only by `setup_db.py`. |
| `waste_admin` | database owner | Full control of `waste_bin`. Use it in pgAdmin/psql. |
| `waste_app` | used by the app | Read `waste_readings`; read and add users. Cannot delete, drop or change data. |
| app users (admin / viewer) | rows in `app_users` | Log in to the Admin tab. Passwords are stored as salted PBKDF2 hashes. |

## Troubleshooting
- **connection refused / timeout:** the service is stopped, or the port in `.env` is wrong (`DB_PORT`).
- **password authentication failed for user "postgres":** `PG_SUPERPASS` is wrong.
- **role/database already exists:** fine, the script updates what exists.
- **ModuleNotFoundError: psycopg:** run `pip install -r requirements-dev.txt` inside the activated environment.
- **The Admin tab says PostgreSQL is not reachable:** the Predict tab still works. Fix the error shown and reload.
