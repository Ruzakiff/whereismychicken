import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.neighbors import NearestNeighbors
import pytz
import pickle

# Load the data
data = pd.read_csv('grouped_cooking_sessions.csv', parse_dates=['start_time', 'expected_end_time', 'leftovers_time', 'end_time'])

# Remove rows with NaN values
data = data.dropna(subset=['end_time', 'leftovers'])

# Convert times to Eastern Time
eastern = pytz.timezone('US/Eastern')
for col in ['start_time', 'expected_end_time', 'leftovers_time', 'end_time']:
    data[col] = data[col].dt.tz_convert(eastern)

# Preprocess the data
data['day_of_week'] = data['start_time'].dt.dayofweek
data['hour'] = data['start_time'].dt.hour

# Function to find the next oven finish time and leftovers for a specific oven
def find_next_oven(current_time, day_of_week, oven):
    future_sessions = data[(data['end_time'] > current_time) & (data['day_of_week'] == day_of_week) & (data['oven'] == oven)]
    if future_sessions.empty:
        return None, None
    next_session = future_sessions.iloc[0]
    return next_session['end_time'], next_session['leftovers']

# Function to get feature importance
def get_feature_importance(model):
    importance = model.feature_importances_
    features = ['Hour', 'Minute', 'Day of Week']
    return dict(zip(features, importance))

# Function to find most similar historical data points
def find_similar_datapoints(X, current_data, n_neighbors=3):
    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean').fit(X)
    distances, indices = nbrs.kneighbors([current_data])
    return indices[0]

# Prepare training data for each oven
ovens = data['oven'].unique()
models = {}
oven_data_dict = {}

for oven in ovens:
    X = []
    y_time = []
    y_leftovers = []

    oven_data = data[data['oven'] == oven]
    for _, row in oven_data.iterrows():
        current_time = row['start_time']
        day_of_week = row['day_of_week']
        next_time, leftovers = find_next_oven(current_time, day_of_week, oven)
        if next_time is not None:
            X.append([current_time.hour, current_time.minute, day_of_week])
            y_time.append((next_time - current_time).total_seconds() / 60)
            y_leftovers.append(leftovers)

    X = np.array(X)
    y_time = np.array(y_time)
    y_leftovers = np.array(y_leftovers)

    oven_data_dict[oven] = {'X': X, 'y_time': y_time, 'y_leftovers': y_leftovers}

    # Train models
    rf_time = RandomForestRegressor(n_estimators=50, random_state=42)
    rf_time.fit(X, y_time)

    rf_leftovers = RandomForestRegressor(n_estimators=50, random_state=42)
    rf_leftovers.fit(X, y_leftovers)

    models[oven] = {'time': rf_time, 'leftovers': rf_leftovers}

# Save the models and oven_data_dict
with open('chicken_models.pkl', 'wb') as f:
    pickle.dump({'models': models, 'oven_data_dict': oven_data_dict}, f)

# Function to predict next oven time and leftovers for all ovens
def predict_next_ovens(current_time):
    hour = current_time.hour
    minute = current_time.minute
    day_of_week = current_time.weekday()
    
    input_data = np.array([[hour, minute, day_of_week]])
    
    predictions = {}
    for oven, model in models.items():
        time_to_next = model['time'].predict(input_data)[0]
        leftovers = model['leftovers'].predict(input_data)[0]
        next_time = current_time + timedelta(minutes=time_to_next)
        
        time_importance = get_feature_importance(model['time'])
        leftovers_importance = get_feature_importance(model['leftovers'])
        
        similar_indices = find_similar_datapoints(oven_data_dict[oven]['X'], input_data[0])
        similar_data = oven_data_dict[oven]['X'][similar_indices]
        similar_times = oven_data_dict[oven]['y_time'][similar_indices]
        similar_leftovers = oven_data_dict[oven]['y_leftovers'][similar_indices]
        
        predictions[oven] = {
            'next_time': next_time,
            'leftovers': leftovers,
            'time_importance': time_importance,
            'leftovers_importance': leftovers_importance,
            'similar_data': similar_data,
            'similar_times': similar_times,
            'similar_leftovers': similar_leftovers
        }
    
    return predictions

# Example usage
current_time = datetime.now(eastern).replace(hour=12, minute=0, second=0, microsecond=0)
predictions = predict_next_ovens(current_time)

print(f"\nCurrent time (Eastern): {current_time.strftime('%Y-%m-%d %I:%M %p')}")
for oven, prediction in predictions.items():
    print(f"\nOven {oven}:")
    print(f"Predicted next finish time (Eastern): {prediction['next_time'].strftime('%Y-%m-%d %I:%M %p')}")
    print(f"Predicted leftovers: {prediction['leftovers']:.2f}")
    
    print("\nTime Prediction Feature Importance:")
    for feature, importance in prediction['time_importance'].items():
        print(f"  {feature}: {importance:.4f}")
    
    print("\nLeftovers Prediction Feature Importance:")
    for feature, importance in prediction['leftovers_importance'].items():
        print(f"  {feature}: {importance:.4f}")
    
    print("\nMost Similar Historical Data Points:")
    for i, (data_point, time, leftovers) in enumerate(zip(prediction['similar_data'], prediction['similar_times'], prediction['similar_leftovers']), 1):
        print(f"  {i}. Input: Hour={data_point[0]}, Minute={data_point[1]}, Day={data_point[2]}")
        print(f"     Output: Time to next finish={time:.2f} minutes, Leftovers={leftovers:.2f}")

        print(f"  {i}. Input: Hour={data_point[0]}, Minute={data_point[1]}, Day={data_point[2]}")
        print(f"     Output: Time to next finish={time:.2f} minutes, Leftovers={leftovers:.2f}")

