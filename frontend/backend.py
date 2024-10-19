from flask import Flask, jsonify
import pickle
from datetime import datetime, timedelta
import pytz
import numpy as np
from sklearn.neighbors import NearestNeighbors

app = Flask(__name__)

# Load the saved models
with open('chicken_models.pkl', 'rb') as f:
    saved_data = pickle.load(f)
    models = saved_data['models']
    oven_data_dict = saved_data['oven_data_dict']

# Function to get feature importance
def get_feature_importance(model):
    importance = model.feature_importances_
    features = ['Hour', 'Minute', 'Day of Week']
    return dict(zip(features, importance.tolist()))  # Convert numpy array to list

# Function to find most similar historical data points
def find_similar_datapoints(X, current_data, n_neighbors=3):
    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean').fit(X)
    distances, indices = nbrs.kneighbors([current_data])
    return indices[0]

# Function to check if a given time is within operating hours
def is_within_operating_hours(time):
    day_of_week = time.weekday()
    hour = time.hour
    
    operating_hours = {
        0: (10, 20),  # Monday
        1: (10, 20),  # Tuesday
        2: (10, 20),  # Wednesday
        3: (10, 20),  # Thursday
        4: (10, 20),  # Friday
        5: (9, 20),   # Saturday
        6: (10, 18)   # Sunday
    }
    
    open_hour, close_hour = operating_hours[day_of_week]
    return open_hour <= hour < close_hour

# Function to get the next open time
def get_next_open_time(current_time):
    while not is_within_operating_hours(current_time):
        current_time += timedelta(hours=1)
        current_time = current_time.replace(minute=0, second=0, microsecond=0)
    return current_time

# Function to get closing time
def get_closing_time(current_time):
    day_of_week = current_time.weekday()
    operating_hours = {
        0: (10, 20),  # Monday
        1: (10, 20),  # Tuesday
        2: (10, 20),  # Wednesday
        3: (10, 20),  # Thursday
        4: (10, 20),  # Friday
        5: (9, 20),   # Saturday
        6: (10, 18)   # Sunday
    }
    _, close_hour = operating_hours[day_of_week]
    return current_time.replace(hour=close_hour, minute=0, second=0, microsecond=0)

# Function to predict next oven time and leftovers for all ovens
def predict_next_ovens(current_time):
    hour = current_time.hour
    minute = current_time.minute
    day_of_week = current_time.weekday()
    
    input_data = np.array([[hour, minute, day_of_week]])
    
    predictions = {}
    for oven, model in models.items():
        time_to_next = float(model['time'].predict(input_data)[0])  # Convert to float
        leftovers = float(model['leftovers'].predict(input_data)[0])  # Convert to float
        next_time = current_time + timedelta(minutes=time_to_next)
        
        time_importance = get_feature_importance(model['time'])
        leftovers_importance = get_feature_importance(model['leftovers'])
        
        similar_indices = find_similar_datapoints(oven_data_dict[oven]['X'], input_data[0])
        similar_data = oven_data_dict[oven]['X'][similar_indices].tolist()
        similar_times = oven_data_dict[oven]['y_time'][similar_indices].tolist()
        similar_leftovers = oven_data_dict[oven]['y_leftovers'][similar_indices].tolist()
        
        predictions[str(oven)] = {  # Convert oven to string
            'next_time': next_time,
            'leftovers': leftovers,
            'time_importance': time_importance,
            'leftovers_importance': leftovers_importance,
            'similar_data': similar_data,
            'similar_times': similar_times,
            'similar_leftovers': similar_leftovers
        }
    
    return predictions

# Function to format predictions based on operating hours
def format_predictions(predictions, current_time):
    formatted_predictions = {}
    closing_time = get_closing_time(current_time)
    time_to_close = (closing_time - current_time).total_seconds() / 60  # in minutes

    if is_within_operating_hours(current_time):
        if time_to_close <= 30:  # If within 30 minutes of closing
            last_batch = find_last_batch(predictions)
            if last_batch:
                for oven, prediction in last_batch.items():
                    formatted_predictions[oven] = {
                        'next_time': None,
                        'leftovers': prediction['leftovers'],
                        'message': f"Last batch: {prediction['leftovers']:.0f} leftovers, {time_to_close:.0f} minutes until close"
                    }
            else:
                for oven in predictions:
                    formatted_predictions[oven] = {
                        'next_time': None,
                        'leftovers': None,
                        'message': f"No recent batches, {time_to_close:.0f} minutes until close"
                    }
        else:
            for oven, prediction in predictions.items():
                if is_within_operating_hours(prediction['next_time']):
                    formatted_predictions[oven] = prediction
                else:
                    formatted_predictions[oven] = {
                        'next_time': None,
                        'leftovers': None,
                        'message': "No more ovens expected to finish before closing time"
                    }
    else:
        next_open_time = get_next_open_time(current_time)
        for oven in predictions:
            formatted_predictions[oven] = {
                'next_time': None,
                'leftovers': None,
                'message': f"Closed. Opens at {next_open_time.strftime('%I:%M %p')} on {next_open_time.strftime('%A')}"
            }
    return formatted_predictions

def find_last_batch(predictions):
    last_batch = {}
    latest_time = datetime.min.replace(tzinfo=pytz.UTC)
    for oven, prediction in predictions.items():
        if prediction['next_time'] > latest_time:
            latest_time = prediction['next_time']
            last_batch = {oven: prediction}
        elif prediction['next_time'] == latest_time:
            last_batch[oven] = prediction
    return last_batch if last_batch else None

@app.route('/predict', methods=['GET'])
def get_predictions():
    eastern = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern)
    raw_predictions = predict_next_ovens(current_time)
    formatted_predictions = format_predictions(raw_predictions, current_time)
    
    # Convert datetime objects to strings for JSON serialization
    for oven, pred in formatted_predictions.items():
        if pred['next_time'] is not None:
            pred['next_time'] = pred['next_time'].isoformat()
    
    return jsonify({
        'current_time': current_time.isoformat(),
        'is_open': is_within_operating_hours(current_time),
        'predictions': formatted_predictions
    })

if __name__ == '__main__':
    app.run(debug=True)
