import json
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

import db

ART = Path(__file__).parent / "artifacts"
st.set_page_config(page_title="Smart Waste-Bin", page_icon="🗑️", layout="centered")


@st.cache_data
def load_metrics():
    return json.load(open(ART / "metrics.json"))


def predict_hours(metrics, fill, weight, now, last_collection):
    """Multiple Linear Regression: intercept + sum(coefficient * feature). Uses the numbers saved in metrics.json."""
    hours_since = max((now - last_collection).total_seconds() / 3600, metrics.get("min_hours", 1))
    x = {
        "fill_pct": fill,
        "weight_kg": weight,
        "hours_since_collection": hours_since,
        "avg_fill_rate": fill / hours_since,
        "hour": now.hour,
        "is_weekend": int(now.weekday() >= 5),
    }
    prediction = metrics["intercept"] + sum(coef * x[name] for name, coef in metrics["coefficients"].items())
    return max(float(prediction), 0.0), hours_since


st.title("🗑️ Smart Waste-Bin System")
st.caption("Predicts how long until the bin is full (Multiple Linear Regression)")

if not (ART / "metrics.json").exists():
    st.error("Model not found. Run the training notebook first so it creates the `artifacts/` folder.")
    st.stop()

metrics = load_metrics()
FULL_LEVEL = metrics.get("full_level_pct", 80)
if "history" not in st.session_state:
    st.session_state.history = []

tab1, tab2, tab3 = st.tabs(["Predict", "Model and data", "Admin"])

with tab1:
    c1, c2 = st.columns(2)
    fill = c1.slider("Current fill level (%)", 0, 100, 40)
    weight = c2.number_input("Current weight (kg)", 0.0, 100.0, 8.0, step=0.5)

    st.markdown("**Last collection (when the bin was emptied)**")
    d1, d2 = st.columns(2)
    default_last = dt.datetime.now() - dt.timedelta(hours=24)
    last_date = d1.date_input("Date", default_last.date())
    last_time = d2.time_input("Time", default_last.time().replace(second=0, microsecond=0))

    use_now = st.checkbox("Use current time as 'now'", value=True)
    if use_now:
        now = dt.datetime.now()
    else:
        n1, n2 = st.columns(2)
        now = dt.datetime.combine(n1.date_input("Now: date", dt.date.today()),
                                  n2.time_input("Now: time", dt.datetime.now().time().replace(second=0, microsecond=0)))
    last_collection = dt.datetime.combine(last_date, last_time)

    if st.button("Predict level until full", type="primary"):
        if last_collection >= now:
            st.error("The last collection must be before the current time.")
        else:
            threshold = FULL_LEVEL
            hours, since = predict_hours(metrics, fill, weight, now, last_collection)
            st.progress(fill / 100, text=f"Fill level: {fill}%")
            if fill >= threshold:
                st.error(f"Bin is already at or above {threshold}%. Collect now.")
                result = "Full: collect now"
            else:
                h, m = int(hours), int(round((hours % 1) * 60))
                st.metric("Estimated time until full", f"{h} h {m} min")
                st.write(f"Expected full around **{(now + dt.timedelta(hours=hours)):%a %d %b, %H:%M}**")
                if hours <= 6:
                    st.warning("Collect soon.")
                else:
                    st.success("No urgent collection needed.")
                result = f"{h} h {m} min"
            st.session_state.history.append({
                "Time": f"{now:%d %b %H:%M}", "Fill %": fill, "Weight kg": weight})

    if st.session_state.history:
        st.markdown("**This session**")
        st.dataframe(pd.DataFrame(st.session_state.history), hide_index=True)

with tab2:
    st.write(f"**Data source:** {metrics['data_source']}  |  **Rows used:** {metrics['rows']}")
    st.write(f"**Weight:** {metrics['weight']}")
    st.write(f"Bin counts as full at **{FULL_LEVEL:.0f}%**.")
    st.markdown("**Test-set results (hours)**")
    st.dataframe(pd.DataFrame({"Baseline (fill % only)": metrics["baseline"],
                               "MLR (all features)": metrics["mlr"],
                               "Ridge": metrics["ridge"]}).T)
    st.markdown("**Regression equation coefficients**")
    st.dataframe(pd.Series(metrics["coefficients"], name="coefficient").round(4).to_frame())
    st.caption(f"Intercept: {metrics['intercept']:.3f}")
    for img in ("eda.png", "evaluation.png"):
        if (ART / img).exists():
            st.image(str(ART / img))

with tab3:
    st.subheader("Database access")
    state = db.status()
    mode = state["mode"]

    if mode == "error":
        st.error(f"The database is configured but not working: {state['message']}")
        st.caption("The Predict and Model tabs still work. Check DATABASE_URL in the app's Secrets.")
    else:
        if mode == "sqlite":
            st.info("Demo mode: PostgreSQL is connected, so this tab shows to Admin bundled read-only copy of the data and a downloadable .csv file. "
                    "You don't need to Signup insteady you have to Login by Credential registered in the Settings.")
        can_login = mode == "postgres" or db.demo_login_configured()
        if not can_login:
            st.warning("Admin login is not set up. Add APP_ADMIN_USER and APP_ADMIN_PASSWORD to the app's Secrets.")

        st.session_state.setdefault("fails", 0)
        if can_login and "user" not in st.session_state:
            if st.session_state.fails >= 5:
                st.error("Too many failed attempts in this session. Reload the page to try again.")
            else:
                with st.form("login"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Log in")
                if submitted:
                    role = db.authenticate(username.strip(), password)
                    if role:
                        st.session_state.user, st.session_state.role, st.session_state.fails = username.strip(), role, 0
                        st.rerun()
                    else:
                        st.session_state.fails += 1
                        st.error("Wrong username or password.")
        elif can_login:
            c1, c2 = st.columns([3, 1])
            c1.write(f"Logged in as **{st.session_state.user}** ({st.session_state.role})")
            if c2.button("Log out"):
                for key in ("user", "role"):
                    st.session_state.pop(key, None)
                st.rerun()

            st.markdown("**Table `waste_readings`**")
            st.write(f"{db.count_readings()} rows")
            limit = st.slider("Rows to show", 10, 500, 50)
            cols = db.READING_COLUMNS
            st.dataframe(pd.DataFrame(db.fetch_readings(limit), columns=cols), hide_index=True)
            st.download_button("Download all rows (CSV)",
                               pd.DataFrame(db.fetch_readings(), columns=cols).to_csv(index=False),
                               "waste_readings.csv", "text/csv")

            if mode == "postgres" and st.session_state.role == "admin":
                st.divider()
                st.markdown("**User management (admin only)**")
                st.dataframe(pd.DataFrame(db.list_users(), columns=["username", "role", "created"]), hide_index=True)
                with st.form("new_user", clear_on_submit=True):
                    n1, n2, n3 = st.columns(3)
                    new_name = n1.text_input("New username")
                    new_pw = n2.text_input("Password (8+ characters)", type="password")
                    new_role = n3.selectbox("Role", list(db.ROLES))
                    if st.form_submit_button("Create user"):
                        try:
                            db.create_user(new_name.strip(), new_pw, new_role)
                            st.success(f"User '{new_name.strip()}' created.")
                        except Exception as exc:
                            st.error(f"Could not create user: {exc}")
