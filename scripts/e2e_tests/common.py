import requests
import time
import sqlite3
import json # For printing dicts nicely

API_BASE_URL = "http://localhost:8000" # Assuming default FastAPI port
DB_PATH = "novel_api_main.db" # Adjusted to match the DB used by FastAPI app in main.py

def post_api(endpoint, payload):
    response = requests.post(f"{API_BASE_URL}{endpoint}", json=payload)
    response.raise_for_status() # Raise an exception for HTTP errors
    return response.json()

def get_api(endpoint):
    response = requests.get(f"{API_BASE_URL}{endpoint}")
    response.raise_for_status()
    return response.json()

def poll_status(novel_id, expected_final_status="completed", timeout_secs=300, poll_interval_secs=10):
    start_time = time.time()
    last_status_data = {}
    while time.time() - start_time < timeout_secs:
        print(f"Polling status for novel_id {novel_id}...")
        try:
            status_data = get_api(f"/novels/{novel_id}/status")
            last_status_data = status_data
            print(f"Current status: {status_data.get('status')}, Current step: {status_data.get('current_step')}") # Changed workflow_status to status
            if status_data.get("status") == expected_final_status:
                print(f"Novel {novel_id} reached expected status: {expected_final_status}")
                return status_data
            if status_data.get("status") in ["failed", "system_error", "system_error_resuming_task", "resumption_critical_error"]: # Added more failure states
                raise Exception(f"Novel {novel_id} failed. Status: {status_data.get('status')}, Error: {status_data.get('error_message')}, Step: {status_data.get('current_step')}")
        except requests.exceptions.HTTPError as e:
            print(f"Polling error for novel_id {novel_id}: {e}. Retrying...")
        except Exception as e: # Catch other errors during polling like network issues
            print(f"An unexpected error occurred during polling for novel_id {novel_id}: {e}. Retrying...")

        time.sleep(poll_interval_secs)
    raise TimeoutError(f"Novel {novel_id} did not reach status '{expected_final_status}' within {timeout_secs}s. Last status: {last_status_data.get('status')}, Last step: {last_status_data.get('current_step')}")

def query_db(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def count_db_records(table_name, novel_id_column, novel_id_value):
    rows = query_db(f"SELECT COUNT(*) as count FROM {table_name} WHERE {novel_id_column} = ?", (novel_id_value,))
    return rows[0]['count'] if rows else 0
