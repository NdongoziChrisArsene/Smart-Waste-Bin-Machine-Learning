# Smart Waste-Bin System: time until the bin is full

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
1. Create and activate an environment, then `pip install -r requirements.txt`
2. Run the notebook (Kernel > Restart Kernel and Run All Cells). It recreates `artifacts/`.
3. PostgreSQL: follow `DATABASE_SETUP.md` (`.env`, then `python setup_db.py`)
4. `streamlit run app.py`

The Predict tab works without PostgreSQL. Only the Admin tab needs it.

## Method
- Cleaning: duplicates removed, sensor spikes removed, short gaps interpolated.
- Collections are detected where smoothed fill % drops by more than 20 points (this bin is emptied about weekly).
- "Full" level = 90% of the bin's typical peak fill (about 46% in this dataset). Change `FULL_THRESHOLD` in the notebook to use a fixed value.
- Target `hours_to_full`; features: fill %, weight (simulated, the dataset has none), hours since collection, average fill rate, hour, weekend flag.
- Time-based split (oldest 80% train, newest 20% test). Metrics: MAE, RMSE, R2.
