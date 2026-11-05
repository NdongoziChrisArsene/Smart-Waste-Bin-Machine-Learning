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
st.caption("Shows how much room is left in the bin and when it reaches the collection level (Multiple Linear Regression)")

if not (ART / "metrics.json").exists():
    st.error("Model not found. Run the training notebook first so it creates the `artifacts/` folder.")
    st.stop()

metrics = load_metrics()
FULL_LEVEL = metrics.get("full_level_pct", 80)
if "history" not in st.session_state:
    st.session_state.history = []

tab1, tab2, tab3 = st.tabs(["Predict", "Model and data", "Admin"])

with tab1:
    CAP_KG = float(metrics.get("bin_capacity_kg", 200))
    SOON_LEVEL = FULL_LEVEL - 15

    weight = st.number_input(f"Current weight in the bin (kg). The bin holds {CAP_KG:.0f} kg when 100% full.",
                             0.0, CAP_KG, 40.0, step=1.0)
    fill = round(weight / CAP_KG * 100, 1)                       # the fill level is calculated from the weight
    f1, f2 = st.columns(2)
    f1.metric("Current fill level (automatic)", f"{fill:.1f} %")
    f2.metric("Collection level", f"{FULL_LEVEL:.0f} %  ({FULL_LEVEL / 100 * CAP_KG:.0f} kg)")
    st.progress(min(fill / 100, 1.0), text=f"{weight:.0f} kg of {CAP_KG:.0f} kg")

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

    if st.button("Predict remaining level", type="primary"):
        if last_collection >= now:
            st.error("The last collection must be before the current time.")
        else:
            remaining = max(FULL_LEVEL - fill, 0.0)                  # % left before the collection level
            free_space = max(100 - fill, 0.0)                        # % of the whole bin still empty
            r1, r2 = st.columns(2)
            r1.metric(f"Level remaining before collection ({FULL_LEVEL:.0f}%)", f"{remaining:.1f} %")
            r1.caption(f"about {remaining / 100 * CAP_KG:.0f} kg more can be added")
            r2.metric("Free space in the bin", f"{free_space:.1f} %")
            r2.caption(f"about {free_space / 100 * CAP_KG:.0f} kg of {CAP_KG:.0f} kg")
            if fill >= FULL_LEVEL:
                st.error(f"The bin reached the {FULL_LEVEL:.0f}% collection level. Collect now.")
            elif fill >= SOON_LEVEL:
                st.warning("Collect soon: the bin is close to the collection level.")
            else:
                st.success("No collection needed yet.")
                hours, since = predict_hours(metrics, fill, weight, now, last_collection)
                h, m = int(hours), int(round((hours % 1) * 60))
                st.caption(f"Model estimate (Multiple Linear Regression): about {h} h {m} min until the bin "
                           f"reaches the {FULL_LEVEL:.0f}% collection level.")
            st.session_state.history.append({
                "Time": f"{now:%d %b %H:%M}", "Weight kg": weight, "Fill %": fill, "Remaining %": round(remaining, 1)})

    if st.session_state.history:
        st.markdown("**This session**")
        st.dataframe(pd.DataFrame(st.session_state.history), hide_index=True)

with tab2:
    st.write(f"**Data source:** {metrics['data_source']}  |  **Rows used:** {metrics['rows']}")
    st.write(f"**Weight:** {metrics['weight']}")
    st.write(f"Bin capacity: **{metrics.get('bin_capacity_kg', 200):.0f} kg** (= 100% fill). Collection level: **{FULL_LEVEL:.0f}%**.")
    if metrics.get("calibrated"):
        st.caption(f"Fill % means percent of the bin's capacity. In this dataset a sensor reading of "
                   f"{metrics['raw_capacity_pct']}% (the bin's usual weekly peak) counts as 100%.")
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
            st.info("Demo mode: PostgreSQL is not connected, so this tab shows the bundled read-only copy of the data "
                    "and a downloadable CSV file. There is no sign-up: log in with the admin credentials saved in "
                    "the app's Secrets.")
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
