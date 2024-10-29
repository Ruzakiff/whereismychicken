from flask import Flask, jsonify, render_template, request
import pickle
from datetime import datetime, timedelta, time
import pytz
import numpy as np
from queue import Queue
from flask import Response
import os
from urllib.parse import unquote
# Add near the top with other imports
STATIC_SCHEDULE_DIR = os.path.join(os.path.dirname(__file__), 'staticschedule')

app = Flask(__name__, template_folder='.')

# Load the saved models
with open('chicken_models.pkl', 'rb') as f:
    saved_data = pickle.load(f)
    models = saved_data['models']

# Define the Eastern timezone
eastern = pytz.timezone('US/Eastern')

# Global variables
current_prediction = None
last_ml_prediction_time = None
oven_details = [{'time': '--:--', 'status': 'Idle', 'leftovers': '--'} for _ in range(4)]
clients = []
last_manual_update = None

ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')
if not ADMIN_TOKEN:
    raise ValueError("ADMIN_TOKEN environment variable must be set")

def get_opening_time(date):
    day_of_week = date.weekday()
    if day_of_week == 6:  # Sunday
        opening_time = time(10, 0)
    else:
        opening_time = time(8, 0)
    naive_datetime = datetime.combine(date, opening_time)
    return eastern.localize(naive_datetime)

def get_closing_time(date):
    if date.weekday() == 6:  # Sunday
        closing_time = time(18, 0)  # 6 PM closing time on Sundays
    else:
        closing_time = time(20, 0)  # 8 PM closing time for other days
    naive_datetime = datetime.combine(date, closing_time)
    return eastern.localize(naive_datetime)

def get_last_batch_time(date):
    return get_closing_time(date) - timedelta(minutes=20)  # No batches in last 30 minutes

def is_within_operating_hours(current_time):
    opening_time = get_opening_time(current_time.date())
    closing_time = get_closing_time(current_time.date())
    return opening_time <= current_time < closing_time

def predict_using_ml(prediction_time):
    hour = prediction_time.hour
    minute = prediction_time.minute
    day_of_week = prediction_time.weekday()
    
    input_data = np.array([[hour, minute, day_of_week]])
    
    earliest_time = None
    oven_predictions = []
    for i, (oven, model) in enumerate(models.items()):
        time_to_next = float(model['time'].predict(input_data)[0])  # in minutes
        next_time = prediction_time + timedelta(minutes=time_to_next)
        leftovers = float(model['leftovers'].predict(input_data)[0])
        
        oven_predictions.append({
            'oven': i + 1,
            'next_time': next_time,
            'leftovers': round(leftovers, 2)
        })
        
        if earliest_time is None or next_time < earliest_time:
            earliest_time = next_time
    
    return earliest_time, oven_predictions

def adjust_prediction(prediction, base_time):
    if not is_within_operating_hours(prediction):
        next_opening = get_opening_time(prediction.date() + timedelta(days=1))
        return next_opening

    last_batch = get_last_batch_time(prediction.date())
    if prediction > last_batch:
        if base_time.date() == prediction.date():
            if prediction.weekday() == 6:  # Sunday
                return prediction  # Allow predictions within buffer on Sundays
            else:
                return None  # No more ovens for the day
        else:
            return get_opening_time(prediction.date())

    return prediction

def predict_next_oven_time(force_new_prediction=False):
    global last_ml_prediction_time, current_prediction, oven_details

    current_time = datetime.now(eastern)
    opening_time = get_opening_time(current_time.date())
    
    # If we're past opening time and no batches reported today,
    # simulate from opening time
    if current_time > opening_time:
        if not last_ml_prediction_time or last_ml_prediction_time.date() != current_time.date():
            prediction_time = opening_time
        else:
            prediction_time = last_ml_prediction_time
    else:
        # If before opening time, start from opening time
        prediction_time = opening_time
        return opening_time

    # Changed condition to handle None case
    if (force_new_prediction or 
        last_ml_prediction_time is None or 
        current_prediction is None or 
        current_time >= current_prediction):
        
        next_oven_time = None
        # Initialize oven_predictions outside the loop
        _, oven_predictions = predict_using_ml(prediction_time)

        while prediction_time <= current_time:
            next_oven_time, oven_predictions = predict_using_ml(prediction_time)
            next_oven_time = adjust_prediction(next_oven_time, prediction_time)
            
            if next_oven_time is None or next_oven_time > current_time:
                break
            
            prediction_time = next_oven_time

        # Update oven_details
        for pred in oven_predictions:
            i = pred['oven'] - 1
            if pred['next_time'] and pred['next_time'] > current_time:
                time_diff = pred['next_time'] - current_time
                time_str = f"{time_diff.seconds // 60:02d}:{time_diff.seconds % 60:02d}"
                status = 'Active'
            else:
                time_str = '--:--'
                status = 'Idle'

            oven_details[i] = {
                'time': time_str,
                'status': status,
                'leftovers': pred['leftovers']
            }

        last_ml_prediction_time = current_time
        current_prediction = next_oven_time

    return current_prediction

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['GET'])
def get_predictions():
    next_oven_time = predict_next_oven_time()
    current_time = datetime.now(eastern)
    
    # Calculate how old the last manual update is
    is_confirmed = False
    if last_manual_update:
        time_since_update = current_time - last_manual_update
        is_confirmed = time_since_update.total_seconds() < 5400  # 90 minutes in seconds
    
    return jsonify({
        'current_time': current_time.isoformat(),
        'is_open': is_within_operating_hours(current_time),
        'earliest_time': next_oven_time.isoformat() if next_oven_time else None,
        'is_sunday': current_time.weekday() == 6,
        'last_manual_update': last_manual_update.isoformat() if last_manual_update else None,
        'is_confirmed': is_confirmed
    })

@app.route('/report-actual-time', methods=['POST'])
def report_actual_time():
    global current_prediction, last_ml_prediction_time, last_manual_update
    data = request.json
    app.logger.info(f'Received data: {data}')
    actual_time = datetime.fromisoformat(data['actual_time']).astimezone(eastern)
    current_time = datetime.now(eastern)
    
    if actual_time > current_time:
        # Future time: just set it directly
        next_oven_time = adjust_prediction(actual_time, current_time)
        message = 'Future time set directly'
    else:
        # Past time: start new prediction chain from this time
        prediction_time = actual_time
        next_oven_time = None
        
        # Chain predictions forward until we get a future time
        while prediction_time <= current_time:
            next_oven_time, oven_predictions = predict_using_ml(prediction_time)
            next_oven_time = adjust_prediction(next_oven_time, prediction_time)
            
            if next_oven_time is None or next_oven_time > current_time:
                break
            
            prediction_time = next_oven_time
            
        message = 'New prediction chain from reported time'
    
    global current_prediction, last_ml_prediction_time
    current_prediction = next_oven_time
    last_ml_prediction_time = actual_time
    last_manual_update = datetime.now(eastern)  # Set the last update time
    
    # Notify all clients of the update
    notify_clients()
    
    return jsonify({
        'status': 'success', 
        'new_prediction': current_prediction.isoformat() if current_prediction else None,
        'message': message,
        'last_update': last_manual_update.isoformat()
    })

@app.route('/oven-status')
def get_oven_status():
    predict_next_oven_time()  # Ensure we have the latest prediction
    return jsonify(oven_details)

@app.route('/ovens')
def ovens():
    return render_template('ovens.html')

@app.route('/admin/<token>')
def admin(token):
    # Decode the token in case it was URL encoded
    decoded_token = unquote(token)
    if decoded_token != ADMIN_TOKEN:
        return "Unauthorized", 401
    return render_template('admin.html')

def notify_clients():
    app.logger.info(f'Notifying {len(clients)} clients')
    for client in clients[:]:
        try:
            client.put("update")
            app.logger.info('Successfully notified a client')
        except:
            clients.remove(client)
            app.logger.info('Removed disconnected client')

@app.route('/events')
def events():
    def stream():
        client = Queue()
        clients.append(client)
        try:
            while True:
                message = client.get()
                yield f"data: {message}\n\n"
        finally:
            clients.remove(client)
    
    return Response(stream(), mimetype='text/event-stream')

@app.route('/schedule')
def get_schedule():
    current_time = datetime.now(eastern)
    day_of_week = current_time.weekday()  # 0-6 (Monday-Sunday)
    
    try:
        # Read schedule based on weekday/weekend
        filename = 'sunday_schedule.txt' if day_of_week == 6 else 'weekday_schedule.txt'
        filepath = os.path.join(STATIC_SCHEDULE_DIR, filename)
        
        with open(filepath, 'r') as f:
            schedule = [line.strip().split(',') for line in f if line.strip()]
        return jsonify({'schedule': schedule})
    except FileNotFoundError as e:
        print(f"Schedule file not found: {e}")  # For debugging
        return jsonify({'schedule': [], 'error': 'Schedule file not found'}), 404
    except Exception as e:
        print(f"Error loading schedule: {e}")  # For debugging
        return jsonify({'schedule': [], 'error': str(e)}), 500

if __name__ == '__main__':

    app.logger.info('Application starting')
    app.run(host='0.0.0.0', port=5000, debug=False)

