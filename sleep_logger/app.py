# app.py

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import os
import uuid
from functools import wraps
from datetime import datetime, timedelta # NEW: Import datetime and timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here' # IMPORTANT: Change this to a strong, random key in production!

DATA_FILE = 'sleep_log.csv'
CSV_HEADERS = ['id', 'user_id', 'hours_slept', 'bedtime', 'wake_time', 'day']

USERS_FILE = 'users.csv'
USERS_HEADERS = ['user_id', 'password_hash']

# --- NEW: Helper function to calculate wake time on the backend ---
def calculate_wake_time_backend(bedtime_str, hours_slept_float):
    if not bedtime_str or hours_slept_float is None or hours_slept_float <= 0:
        return None # Cannot calculate if inputs are invalid

    try:
        # Parse bedtime string into a datetime.time object
        bedtime_time = datetime.strptime(bedtime_str, '%H:%M').time()
        
        # Create a dummy datetime object for calculation (date doesn't matter, just time)
        # Using a fixed date like 2000-01-01 to easily do arithmetic
        dummy_bedtime_dt = datetime(2000, 1, 1, bedtime_time.hour, bedtime_time.minute)

        # Calculate wake time by adding hours_slept as timedelta
        wake_time_dt = dummy_bedtime_dt + timedelta(hours=hours_slept_float)

        # Format the result back to HH:MM string
        return wake_time_dt.strftime('%H:%M')
    except ValueError:
        return None # Handle invalid time format or other parsing errors

# --- Existing User management helper functions  ---
def read_users():
    """Reads all registered user IDs and their password hashes from the users.csv file."""
    users = {} # Store as dict: {user_id: password_hash}
    if not os.path.exists(USERS_FILE):
        return users
    with open(USERS_FILE, 'r', newline='') as f:
        
        reader = csv.DictReader(f) 
        for row in reader:
            if 'user_id' in row and 'password_hash' in row:
                users[row['user_id']] = row['password_hash']
    return users

def add_user(user_id, password):
    users = read_users()
    if user_id in users:
        return False
    hashed_password = generate_password_hash(password)
    with open(USERS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, hashed_password])
    return True

def write_users_to_csv(users_dict):
    with open(USERS_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=USERS_HEADERS)
        writer.writeheader()
        for user_id, password_hash in users_dict.items():
            writer.writerow({'user_id': user_id, 'password_hash': password_hash})

# Initial users.csv file creation/header write (keep as is)
if not os.path.exists(USERS_FILE) or os.stat(USERS_FILE).st_size == 0:
    with open(USERS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(USERS_HEADERS)
else:
    with open(USERS_FILE, 'r', newline='') as f:
        reader = csv.reader(f)
        try:
            first_row = next(reader)
            if first_row != USERS_HEADERS:
                print(f"WARNING: USERS CSV file '{USERS_FILE}' exists but has incorrect headers. Expected: {USERS_HEADERS}, Found: {first_row}. Consider deleting '{USERS_FILE}' to restart.")
                with open(USERS_FILE, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(USERS_HEADERS)
        except StopIteration:
            with open(USERS_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(USERS_HEADERS)

# --- Existing Sleep Data Helpers (keep as is) ---
def read_sleep_data_from_csv():
    entries = []
    if not os.path.exists(DATA_FILE):
        return entries
    with open(DATA_FILE, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'hours_slept' in row and row['hours_slept']:
                try:
                    row['hours_slept'] = float(row['hours_slept'])
                except ValueError:
                    pass
            entries.append(row)
    return entries

def write_sleep_data_to_csv(entries):
    with open(DATA_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(entries)

if not os.path.exists(DATA_FILE) or os.stat(DATA_FILE).st_size == 0:
    with open(DATA_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
else:
    with open(DATA_FILE, 'r', newline='') as f:
        reader = csv.reader(f)
        try:
            first_row = next(reader)
            if first_row != CSV_HEADERS:
                print(f"WARNING: CSV file '{DATA_FILE}' exists but has incorrect headers. Expected: {CSV_HEADERS}, Found: {first_row}. Data might not be parsed correctly. Consider deleting '{DATA_FILE}' to restart.")
        except StopIteration:
            with open(DATA_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)


# --- Existing Routes (keep as is) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('select_user_page', next=request.url, error="Please log in to access this page."))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def select_user_page():
    if request.method == 'POST':
        user_id = request.form['user_id'].strip()
        password = request.form['password']
        users = read_users()
        if user_id in users and check_password_hash(users[user_id], password):
            session['user_id'] = user_id
            return redirect(url_for('user_dashboard', user_id=user_id))
        else:
            return render_template('user_selection.html', error="Invalid User ID or Password.")
    return render_template('user_selection.html', error=request.args.get('error'), message=request.args.get('message'))

@app.route('/create_user', methods=['GET', 'POST'])
def create_user_page():
    if request.method == 'POST':
        new_user_id = request.form['new_user_id'].strip()
        new_password = request.form['new_password']
        if not new_user_id:
            return render_template('create_user.html', error="User ID cannot be empty.")
        if not new_password:
            return render_template('create_user.html', error="Password cannot be empty.")
        if add_user(new_user_id, new_password):
            return redirect(url_for('select_user_page', message="User created! Please log in."))
        else:
            return render_template('create_user.html', error="User ID already exists. Please choose another.")
    return render_template('create_user.html')

@app.route('/dashboard/<string:user_id>', methods=['GET'])
@login_required
def user_dashboard(user_id):
    if session.get('user_id') != user_id:
        return redirect(url_for('select_user_page', error="Unauthorized access or session mismatch."))
    return render_template('index.html', current_user_id=user_id)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('select_user_page', message="You have been logged out."))

# --- MODIFIED: POST /sleep to calculate wake_time ---
@app.route('/sleep', methods=['POST'])
@login_required
def log_sleep():
    data = request.get_json()
    
    if data.get('user_id') != session.get('user_id'):
        return jsonify({"error": "Unauthorized: Data does not match logged-in user."}), 403

    required_fields = ['user_id', 'hours_slept', 'bedtime', 'day'] # wake_time removed from required
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields. Required: user_id, hours_slept, bedtime, day."}), 400

    bedtime_str = data.get('bedtime')
    hours_slept_float = float(data.get('hours_slept')) # Convert to float for calculation

    calculated_wake_time = calculate_wake_time_backend(bedtime_str, hours_slept_float)
    if calculated_wake_time is None:
        return jsonify({"error": "Invalid bedtime or hours_slept provided for wake time calculation."}), 400

    record_id = str(uuid.uuid4())
    new_record = {
        "id": record_id,
        "user_id": data.get('user_id'),
        "hours_slept": hours_slept_float, # Use float for consistency
        "bedtime": bedtime_str,
        "wake_time": calculated_wake_time, # Store calculated wake_time
        "day": data.get('day')
    }
    entries = read_sleep_data_from_csv()
    entries.append(new_record)
    write_sleep_data_to_csv(entries)
    print(f"Added new sleep record with ID: {record_id}")
    return jsonify({"message": "Sleep data added successfully!", "record": new_record}), 201

# --- MODIFIED: PUT /data/<string:record_id> to calculate wake_time ---
@app.route('/data/<string:record_id>', methods=['PUT'])
@login_required
def update_sleep_data(record_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON and not empty"}), 400

    if data.get('user_id') != session.get('user_id'):
        return jsonify({"error": "Unauthorized: Cannot update data for a different user."}), 403

    entries = read_sleep_data_from_csv()
    updated = False
    updated_record = None
    for i, entry in enumerate(entries):
        if entry.get('id') == record_id:
            if entry.get('user_id') != session.get('user_id'):
                return jsonify({"error": "Unauthorized: Record does not belong to logged-in user."}), 403

            # Flags to check if bedtime or hours_slept were updated
            bedtime_updated = False
            hours_slept_updated = False

            for key, value in data.items():
                if key != 'id' and key in CSV_HEADERS:
                    entries[i][key] = value
                    if key == 'bedtime':
                        bedtime_updated = True
                    elif key == 'hours_slept':
                        hours_slept_updated = True
            
            # Ensure hours_slept is a float in the dict
            if 'hours_slept' in entries[i] and entries[i]['hours_slept']:
                try:
                    entries[i]['hours_slept'] = float(entries[i]['hours_slept'])
                except ValueError:
                    pass # Keep as string if conversion fails, but ideally enforce numerical input
            
            # Recalculate wake_time if bedtime OR hours_slept were changed/provided
            # or if they are the original values and we need to ensure wake_time is correct
            if bedtime_updated or hours_slept_updated:
                new_bedtime = entries[i].get('bedtime')
                new_hours_slept = entries[i].get('hours_slept') # This is already float
                if new_bedtime and new_hours_slept is not None:
                    recalculated_wake_time = calculate_wake_time_backend(new_bedtime, new_hours_slept)
                    if recalculated_wake_time:
                        entries[i]['wake_time'] = recalculated_wake_time
                    else:
                        return jsonify({"error": "Invalid bedtime or hours_slept after update for wake time calculation."}), 400

            updated_record = entries[i]
            updated = True
            break
    if updated:
        write_sleep_data_to_csv(entries)
        print(f"Updated sleep record with ID: {record_id}")
        return jsonify({"message": "Sleep record updated successfully!", "record": updated_record}), 200
    else:
        return jsonify({"error": f"Sleep record with ID {record_id} not found."}), 404


# Existing GET /data, GET /data/<id>, DELETE /data/<id> (keep as is)
@app.route('/data', methods=['GET'])
@login_required
def get_all_sleep_data():
    user_id = request.args.get('user_id')
    if user_id != session.get('user_id'):
        return jsonify({"error": "Unauthorized: Cannot access other users' data."}), 403
    entries = read_sleep_data_from_csv()
    filtered_entries = [entry for entry in entries if entry.get('user_id') == user_id]
    return jsonify(filtered_entries), 200

@app.route('/data/<string:record_id>', methods=['GET'])
@login_required
def get_single_sleep_data(record_id):
    entries = read_sleep_data_from_csv()
    for entry in entries:
        if entry.get('id') == record_id:
            if entry.get('user_id') != session.get('user_id'):
                return jsonify({"error": "Unauthorized: Cannot access this record."}), 403
            return jsonify(entry), 200
    return jsonify({"error": f"Sleep record with ID {record_id} not found."}), 404

@app.route('/data/<string:record_id>', methods=['DELETE'])
@login_required
def delete_sleep_data(record_id):
    entries = read_sleep_data_from_csv()
    initial_count = len(entries)
    found_and_authorized = False
    updated_entries = []
    for entry in entries:
        if entry.get('id') == record_id:
            if entry.get('user_id') == session.get('user_id'):
                found_and_authorized = True
            else:
                return jsonify({"error": "Unauthorized: Cannot delete this record."}), 403
        else:
            updated_entries.append(entry)
    if found_and_authorized:
        write_sleep_data_to_csv(updated_entries)
        print(f"Deleted sleep record with ID: {record_id}")
        return jsonify({"message": f"Sleep record with ID {record_id} deleted successfully."}), 200
    else:
        return jsonify({"error": f"Sleep record with ID {record_id} not found."}), 404


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)