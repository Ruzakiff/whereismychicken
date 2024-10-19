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

@app.route('/predict', methods=['GET'])
def get_predictions():
    eastern = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern)
    predictions = predict_next_ovens(current_time)
    
    # Convert datetime objects to strings for JSON serialization
    for oven, pred in predictions.items():
        pred['next_time'] = pred['next_time'].isoformat()
    
    return jsonify({
        'current_time': current_time.isoformat(),
        'predictions': predictions
    })

if __name__ == '__main__':
    app.run(debug=True)
