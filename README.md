# hospital-bulk-processing-system

Features:
- GET `/` : Landing / health endpoint returning status OK (200)
- POST `/hospitals/bulk/validate` : Validate uploaded CSV file for required headers and max rows
	- Required headers: `name`, `address`
	- Returns JSON `{"status":"valid", "count": N}` on success
- POST `/hospitals/bulk` : Bulk-create hospitals from uploaded CSV
	- Parses CSV and validates each row
	- Calls upstream Hospitals API to create hospital records
	- Records per-row successes and failures and returns a batch summary
	- Attempts to activate the created batch at the upstream service
- CSV parsing and validation
	- UTF-8 CSV parsing with graceful errors for invalid format/encoding
	- Enforces a configurable `MAX_CSV_SIZE` (environment variable)
- Logging and error-handling
	- Logs upstream request failures and exceptions
	- Returns informative HTTP 400 errors for client-side input problems
- Testing
	- Pytest tests in `tests/test_main.py` that mock upstream `requests` calls

Deployment:
- Deployed application URL: https://hospital-bulk-processing-system-yews.onrender.com/

How to run locally:
1. Install dependencies:
	 ```bash
	 pip install -r requirements.txt
	 ```
2. Start the server:
	 ```bash
	 uvicorn main:app --reload
	 ```
3. Endpoints:
	 - `GET /` - health
	 - `POST /hospitals/bulk/validate` - multipart/form-data `csv_file` upload
	 - `POST /hospitals/bulk` - multipart/form-data `csv_file` upload


Repository files of interest:
- `main.py` - main FastAPI app
- `requirements.txt` - Python dependencies
- `tests/test_main.py` - unit tests

Contact / Maintainer: lakshyaakar007@gmail.com