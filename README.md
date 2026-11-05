# Smart Waste-Bin System: level until the bin is full

Multiple Linear Regression trained on the Kaggle "Synthetic Smart City Infrastructure Sensor Data" (waste sensor),
stored in PostgreSQL, deployed as a Streamlit app with an admin login. No Raspberry Pi or circuit needed.

## Folder
- `Smart_Waste_Bin_Training.ipynb`: cleaning, plots, SQLite storage, training, evaluation, saving the model
- `smart_city_sensor_data.csv`: the dataset
- `artifacts/`: model (`bin_model.pkl`), metrics, plots, SQLite file (`waste_bin.db`)
- `app.py`: Streamlit app (Predict, Model and data, Admin tabs)
- `db.py`, `setup_db.py`: PostgreSQL helpers and one-time setup
- `.env.example`: settings template (copy to `.env`, never upload `.env`)
- `DATABASE_SETUP.md`: PostgreSQL steps for Windows

## Run it
1. Create and activate an environment, then `pip install -r requirements-dev.txt`
2. Run the notebook (Kernel > Restart Kernel and Run All Cells). It recreates `artifacts/`.
3. PostgreSQL: follow `DATABASE_SETUP.md` (`.env`, then `python setup_db.py`)
4. `streamlit run app.py`

The Predict tab works without PostgreSQL. Only the Admin tab needs it.

## Method
- Cleaning: duplicates removed, sensor spikes removed, short gaps interpolated.
- Collections are detected where smoothed fill % drops by more than 20 points (this bin is emptied about weekly).
- Fill % is rescaled so the bin's usual weekly peak (about 54% on the raw sensor scale) counts as 100% capacity; "full" is 80% of capacity. In the notebook, `CALIBRATE = False` and `FULL_THRESHOLD = "auto"` restore the raw-scale behaviour (full at about 46%).
- Target `hours_to_full`; features: fill %, weight (simulated, the dataset has none), hours since collection, average fill rate, hour, weekend flag.
- Time-based split (oldest 80% train, newest 20% test). Metrics: MAE, RMSE, R2.

## Weight and fill level
The operator enters the weight (kg). The fill level is calculated automatically: weight / bin capacity (200 kg = 100%).
The app shows the level remaining before the 80% collection level and the free space in the bin.
The capacity is the `BIN_CAPACITY_KG` setting in the notebook; the app reads it from `artifacts/metrics.json`.
