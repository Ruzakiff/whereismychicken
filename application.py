from flask import Flask, jsonify, request, render_template_string, send_from_directory
from datetime import datetime, timedelta
import json
import boto3
from botocore.exceptions import ClientError
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__, static_folder='static')

# S3 configuration
S3_BUCKET = 'chickentraining'
S3_KEY = 'chicken_data.json'
S3_OVEN_STATE_KEY = 'oven_states.json'

# Initialize S3 client
s3 = boto3.client('s3')

# Configure logging
logging.basicConfig(level=logging.INFO)
file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Chicken Tracker startup')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('static/js', path)

@app.route('/', methods=['GET'])
def dashboard():
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chicken Tracker Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }
            .oven { border: 1px solid #ddd; padding: 10px; margin-bottom: 15px; }
            .out-of-service { background-color: #ffcccc; }
            button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; cursor: pointer; margin: 5px; }
            input[type="number"] { width: 60px; }
            #log { height: 200px; overflow-y: scroll; border: 1px solid #ddd; padding: 10px; margin-top: 20px; }
            .oven-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        </style>
    </head>
    <body>
        <h1>Chicken Tracker Dashboard</h1>
        <div class="oven-grid" id="ovens">
            <!-- Oven divs will be dynamically inserted here -->
        </div>
        <div>
            <h2>Quick Actions</h2>
            <button onclick="logSpecialEvent()">Log Special Event</button>
            <button onclick="logWeather()">Log Weather</button>
            <button onclick="logIssue()">Log Issue</button>
        </div>
        <div id="log">
            <h2>Activity Log</h2>
            <ul id="activity-log"></ul>
        </div>
        <script src="/js/dashboard.js"></script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/log_batch', methods=['POST'])
def log_batch():
    data = request.json
    required_fields = ['ovens', 'first_batch_of_shift', 'weather', 'temperature']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Process each oven's data
    for oven in data['ovens']:
        oven['batch_start_time'] = oven['start_time']
        oven['batch_end_time'] = oven['end_time']
        oven['chickens_sold'] = oven['chickens_cooked'] - oven['chickens_leftover']
        
        batch_end = datetime.fromisoformat(oven['batch_end_time'])
        oven['day_of_week'] = batch_end.weekday()
        oven['time_of_day'] = batch_end.strftime('%H:%M')
        oven['is_weekend'] = batch_end.weekday() >= 5
    
    # Load existing data from S3
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        existing_data = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data = []
        else:
            return jsonify({'error': 'Failed to retrieve existing data'}), 500
    
    # If this is the first batch of the shift, add estimated previous batches
    if data['first_batch_of_shift']:
        store_open_time = datetime.fromisoformat(data['ovens'][0]['batch_end_time']).replace(hour=8, minute=0, second=0, microsecond=0)
        estimated_batches = [
            {
                'batch_end_time': store_open_time.isoformat(),
                'batch_start_time': (store_open_time - timedelta(minutes=100)).isoformat(),
                'chickens_cooked': 28,
                'chickens_leftover': 0,
                'chickens_sold': 28,
                'day_of_week': store_open_time.weekday(),
                'time_of_day': store_open_time.strftime('%H:%M'),
                'is_weekend': store_open_time.weekday() >= 5,
                'estimated': True
            }
        ]
        for i in range(1, 3):  # Add two more estimated batches
            end_time = store_open_time + timedelta(minutes=100*i)
            estimated_batches.append({
                'batch_end_time': end_time.isoformat(),
                'batch_start_time': (end_time - timedelta(minutes=100)).isoformat(),
                'chickens_cooked': 84,
                'chickens_leftover': 0,
                'chickens_sold': 84,
                'day_of_week': end_time.weekday(),
                'time_of_day': end_time.strftime('%H:%M'),
                'is_weekend': end_time.weekday() >= 5,
                'estimated': True
            })
        existing_data.extend(estimated_batches)
    
    # Append new data
    existing_data.extend(data['ovens'])
    
    # Sort data by date and time
    existing_data.sort(key=lambda x: x['batch_end_time'])
    
    # Assign batch numbers for each day
    current_date = None
    batch_number = 0
    for entry in existing_data:
        entry_date = datetime.fromisoformat(entry['batch_end_time']).date()
        if entry_date != current_date:
            current_date = entry_date
            batch_number = 1
        else:
            batch_number += 1
        entry['batch_number'] = batch_number
    
    # Save updated data to S3
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json.dumps(existing_data, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
    except ClientError:
        return jsonify({'error': 'Failed to save data'}), 500
    
    app.logger.info(f"Logged batch data: {json.dumps(data)}")
    
    return jsonify({'message': 'Batch logged successfully'}), 200

@app.route('/log', methods=['POST'])
def log_action():
    data = request.json
    action = data.get('action')
    log_data = data.get('data', {})
    
    app.logger.info(f"Logged action: {action}, Data: {json.dumps(log_data)}")
    
    # Load existing data from S3
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        existing_data = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data = []
        else:
            return jsonify({'error': 'Failed to retrieve existing data'}), 500
    
    # Process the log data based on the action
    if action == 'start_cooking':
        log_entry = {
            'action': 'start_cooking',
            'oven': log_data['oven'],
            'chickens': log_data['chickens'],
            'start_time': log_data['start_time'],
            'expected_end_time': log_data['expected_end_time']
        }
    elif action == 'adjust_cooking_time':
        log_entry = {
            'action': 'adjust_cooking_time',
            'oven': log_data['oven'],
            'new_time_left': log_data['new_time_left'],
            'new_expected_end_time': log_data['new_expected_end_time']
        }
    elif action == 'finish_cooking':
        log_entry = {
            'action': 'finish_cooking',
            'oven': log_data['oven'],
            'chickens': log_data['chickens'],
            'start_time': log_data['start_time'],
            'expected_end_time': log_data['expected_end_time'],
            'actual_end_time': log_data['actual_end_time']
        }
    elif action == 'post_rush':
        log_entry = {
            'action': 'post_rush',
            'oven': log_data['oven'],
            'chickens_taken': log_data['chickens_taken'],
            'chickens_left': log_data['chickens_left'],
            'time': log_data['time']
        }
    elif action in ['special_event', 'weather', 'issue']:
        log_entry = {
            'action': action,
            'time': log_data['time'],
            'details': log_data
        }
    else:
        return jsonify({'error': 'Unknown action type'}), 400
    
    # Add timestamp to the log entry
    log_entry['timestamp'] = datetime.now().isoformat()
    
    # Append new data
    existing_data.append(log_entry)
    
    # Save updated data to S3
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json.dumps(existing_data, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
    except ClientError:
        return jsonify({'error': 'Failed to save data'}), 500
    
    return jsonify({'message': 'Action logged successfully'}), 200

@app.route('/', methods=['GET'])
def health_check():
    app.logger.info("Health check request received")
    return jsonify({
        'status': 'healthy',
        'message': 'Chicken Tracker is running'
    }), 200

@app.route('/oven_states', methods=['GET'])
def get_oven_states():
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_OVEN_STATE_KEY)
        oven_states = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            # If the file doesn't exist, create an empty oven states object
            oven_states = {}
            try:
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=S3_OVEN_STATE_KEY,
                    Body=json.dumps(oven_states).encode('utf-8'),
                    ContentType='application/json'
                )
            except ClientError as put_error:
                app.logger.error(f"Error creating oven states file: {str(put_error)}")
                return jsonify({'error': 'Failed to create oven states file'}), 500
        else:
            app.logger.error(f"Error retrieving oven states: {str(e)}")
            return jsonify({'error': 'Failed to retrieve oven states'}), 500
    return jsonify(oven_states)

@app.route('/update_oven_state', methods=['POST'])
def update_oven_state():
    data = request.json
    oven_number = data.get('oven')
    oven_state = data.get('state')
    
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_OVEN_STATE_KEY)
        oven_states = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            # If the file doesn't exist, create an empty oven states object
            oven_states = {}
        else:
            app.logger.error(f"Error retrieving oven states: {str(e)}")
            return jsonify({'error': 'Failed to retrieve oven states'}), 500
    
    oven_states[str(oven_number)] = oven_state
    
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_OVEN_STATE_KEY,
            Body=json.dumps(oven_states, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
    except ClientError as e:
        app.logger.error(f"Error saving oven state: {str(e)}")
        return jsonify({'error': 'Failed to save oven state'}), 500
    
    return jsonify({'message': 'Oven state updated successfully'}), 200

if __name__ == '__main__':
    app.logger.info('Application starting')
    app.run(host='0.0.0.0', port=5000, debug=False)
