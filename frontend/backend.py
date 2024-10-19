from flask import Flask, jsonify, render_template
import pickle
from datetime import datetime, timedelta, time
import pytz
import numpy as np

app = Flask(__name__, template_folder='.')

# Load the saved models
with open('chicken_models.pkl', 'rb') as f:
    saved_data = pickle.load(f)
    models = saved_data['models']

eastern = pytz.timezone('US/Eastern')

# Global variables
current_prediction = None
last_ml_prediction_time = None
CYCLE_DURATION = timedelta(minutes=90)

def get_opening_time(date):
    day_of_week = date.weekday()
    if day_of_week == 6:  # Sunday
        opening_time = time(10, 0)
    else:
        opening_time = time(8, 0)
    naive_datetime = datetime.combine(date, opening_time)
    return eastern.localize(naive_datetime)

def get_closing_time(date):
    closing_time = time(22, 0)  # 10 PM closing time
    naive_datetime = datetime.combine(date, closing_time)
    return eastern.localize(naive_datetime)

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

def predict_next_oven_time(current_time):
    global last_ml_prediction_time, current_prediction

    opening_time = get_opening_time(current_time.date())
    
    if current_time < opening_time:
        return opening_time

    if last_ml_prediction_time is None or current_time >= current_prediction:
        # Backtrack to find the correct prediction
        prediction_time = opening_time
        while True:
            next_oven_time = predict_using_ml(prediction_time)
            if next_oven_time > current_time:
                current_prediction = next_oven_time
                last_ml_prediction_time = prediction_time
                break
            prediction_time = next_oven_time

    return current_prediction

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['GET'])
def get_predictions():
    current_time = datetime.now(eastern)
    next_oven_time = predict_next_oven_time(current_time)
    
    return jsonify({
        'current_time': current_time.isoformat(),
        'is_open': is_within_operating_hours(current_time),
        'earliest_time': next_oven_time.isoformat() if next_oven_time else None
    })

if __name__ == '__main__':
    app.run(debug=True)

