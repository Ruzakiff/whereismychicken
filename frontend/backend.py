from flask import Flask, jsonify, render_template, request
import pickle
from datetime import datetime, timedelta, time
import pytz
import numpy as np

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
CYCLE_DURATION = timedelta(minutes=90)
LAST_BATCH_BUFFER = timedelta(minutes=20)  # No batches in last 30 minutes

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
    return get_closing_time(date) - LAST_BATCH_BUFFER

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
    for oven, model in models.items():
        time_to_next = float(model['time'].predict(input_data)[0])  # in minutes
        next_time = prediction_time + timedelta(minutes=time_to_next)
        
        if earliest_time is None or next_time < earliest_time:
            earliest_time = next_time
    
    return earliest_time

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
    global last_ml_prediction_time, current_prediction

    # Get current time in Eastern Time
    current_time = datetime.now(eastern)
    
    opening_time = get_opening_time(current_time.date())
    
    if current_time < opening_time:
        return opening_time

    if force_new_prediction or last_ml_prediction_time is None or current_time >= current_prediction:
        # Start predictions from opening time
        prediction_time = opening_time
        next_oven_time = None

        while prediction_time <= current_time:
            next_oven_time = predict_using_ml(prediction_time)
            next_oven_time = adjust_prediction(next_oven_time, prediction_time)
            
            if next_oven_time is None or next_oven_time > current_time:
                break
            
            prediction_time = next_oven_time

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
    
    return jsonify({
        'current_time': current_time.isoformat(),
        'is_open': is_within_operating_hours(current_time),
        'earliest_time': next_oven_time.isoformat() if next_oven_time else None,
        'is_sunday': current_time.weekday() == 6
    })

@app.route('/report-actual-time', methods=['POST'])
def report_actual_time():
    app.logger.info('Received request to /report-actual-time')
    data = request.json
    app.logger.info(f'Received data: {data}')
    actual_time = datetime.fromisoformat(data['actual_time']).astimezone(eastern)
    current_time = datetime.now(eastern)
    
    if actual_time > current_time:
        # Reported time is in the future (next expected batch)
        next_oven_time = adjust_prediction(actual_time, current_time)
        message = 'Future time set directly'
    else:
        # Reported time is in the past (last batch that came out)
        # Force a new prediction based on the reported time
        next_oven_time = predict_next_oven_time(force_new_prediction=True)
        message = 'New prediction based on past time'
    
    global current_prediction, last_ml_prediction_time
    current_prediction = next_oven_time
    last_ml_prediction_time = actual_time
    
    app.logger.info(f'New prediction set: {current_prediction.isoformat() if current_prediction else "None"}')
    
    return jsonify({
        'status': 'success', 
        'new_prediction': current_prediction.isoformat() if current_prediction else None,
        'message': message
    })

if __name__ == '__main__':

    app.logger.info('Application starting')
    app.run(host='0.0.0.0', port=5000, debug=False)



