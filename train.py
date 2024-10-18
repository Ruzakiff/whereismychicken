import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
import warnings

#TODO LEARN TIME BETEWEN OVEN STARTS AS BUFER TIME TO LOAD 
# Add this function to suppress warnings
def suppress_warnings():
    warnings.filterwarnings("ignore", category=UserWarning)

# Call this function at the beginning of your script
suppress_warnings()

# Load the data from CSV
data = pd.read_csv('processed_chicken_data.csv')

# Convert timestamp column to datetime using ISO8601 format
data['timestamp'] = pd.to_datetime(data['timestamp'], format='ISO8601')

# Sort the data by timestamp
data = data.sort_values('timestamp')

# Calculate cooking duration
data['cooking_duration'] = data.groupby('oven')['timestamp'].diff().dt.total_seconds() / 60
data['cooking_duration'] = data['cooking_duration'].fillna(0)

# Filter out rows with zero or negative cooking duration
data = data[data['cooking_duration'] > 0]

# Add day_of_week column
data['day_of_week'] = data['timestamp'].dt.dayofweek

# Add hour column
data['hour'] = data['timestamp'].dt.hour

# Function to train model for each oven
def train_oven_model(oven_data):
    X = oven_data[['chickens', 'day_of_week', 'hour']]
    y = oven_data['cooking_duration']
    
    # Remove rows with NaN values
    X = X.dropna()
    y = y[X.index]
    
    # One-hot encode the day_of_week and hour
    encoder = OneHotEncoder(drop='first', sparse_output=False, handle_unknown='ignore')
    encoded = encoder.fit_transform(X[['day_of_week', 'hour']])
    
    # Combine chickens with encoded features
    X_encoded = np.column_stack([X['chickens'], encoded])
    
    # Use SimpleImputer to handle any remaining NaN values
    imputer = SimpleImputer(strategy='mean')
    X_encoded = imputer.fit_transform(X_encoded)
    
    model = LinearRegression()
    model.fit(X_encoded, y)
    
    return model, encoder, imputer

# Train models for each oven
oven_models = {}
for oven in data['oven'].unique():
    oven_data = data[data['oven'] == oven]
    if not oven_data.empty:
        oven_models[oven] = train_oven_model(oven_data)

def get_next_batch_time(oven, current_time):
    oven_data = data[data['oven'] == oven]
    day_of_week = current_time.weekday()
    hour = current_time.hour
    
    # Filter data for the same day of week and future hours
    same_day_data = oven_data[(oven_data['day_of_week'] == day_of_week) & (oven_data['hour'] >= hour)]
    
    if same_day_data.empty:
        # If no data for the same day, look for the next day
        next_day_data = oven_data[oven_data['day_of_week'] == (day_of_week + 1) % 7]
        if next_day_data.empty:
            return None
        next_batch = next_day_data.iloc[0]
        days_ahead = 1
    else:
        next_batch = same_day_data.iloc[0]
        days_ahead = 0
    
    next_time = current_time.replace(hour=next_batch['hour'], minute=next_batch['timestamp'].minute, second=0, microsecond=0)
    if days_ahead > 0:
        next_time += timedelta(days=days_ahead)
    
    return next_time

def predict_time_until_ready(oven, current_time, chickens):
    if oven not in oven_models:
        return "No data available for this oven"
    
    model, encoder, imputer = oven_models[oven]
    day_of_week = current_time.weekday()
    hour = current_time.hour
    
    # Get the next batch time
    next_batch_time = get_next_batch_time(oven, current_time)
    
    if next_batch_time is None:
        return "Unable to predict next batch time"
    
    # Use the hour of the next batch time for prediction
    prediction_hour = next_batch_time.hour
    
    # Prepare input data
    X = pd.DataFrame({'chickens': [chickens], 'day_of_week': [day_of_week], 'hour': [prediction_hour]})
    X_encoded = np.column_stack([X['chickens'], encoder.transform(X[['day_of_week', 'hour']])])
    
    # Predict cooking duration
    predicted_duration = model.predict(X_encoded)[0]
    
    # Calculate predicted finish time
    predicted_finish_time = next_batch_time + timedelta(minutes=predicted_duration)
    
    time_until_ready = (predicted_finish_time - current_time).total_seconds() / 60
    return round(time_until_ready)

# Function to get predictions for all ovens
def get_todays_predictions(chickens=28):
    current_time = datetime.now() #- timedelta(hours=24)
    predictions = {}
    for oven in range(1, 5):
        time_until_ready = predict_time_until_ready(oven, current_time, chickens)
        if isinstance(time_until_ready, int):
            predictions[f'Oven {oven}'] = f"Ready in: {time_until_ready} min"
        else:
            predictions[f'Oven {oven}'] = time_until_ready
    return predictions

# Example usage for today's predictions
today_predictions = get_todays_predictions()
print("Today's predictions:", today_predictions)

# Function to get prediction for a specific oven
def get_oven_prediction(oven, chickens=28):
    current_time = datetime.now() #- timedelta(hours=23)
    time_until_ready = predict_time_until_ready(oven, current_time, chickens)
    if isinstance(time_until_ready, int):
        return f"Ready in: {time_until_ready} min"
    else:
        return time_until_ready

# Example usage for a specific oven
print("\nPrediction for Oven 1:")
print(get_oven_prediction(oven=1))

# Print model coefficients for analysis
print("\nModel coefficients for each oven:")
for oven, (model, encoder, imputer) in oven_models.items():
    print(f"\nOven {oven}:")
    print(f"  Intercept: {model.intercept_:.2f}")
    print(f"  Chickens coefficient: {model.coef_[0]:.2f}")
    feature_names = encoder.get_feature_names_out(['day_of_week', 'hour'])
    for i, feature in enumerate(feature_names):
        print(f"  {feature} coefficient: {model.coef_[i+1]:.2f}")

# Print column names and first few rows for debugging
print("\nColumns in the DataFrame:")
print(data.columns.tolist())
print("\nFirst few rows of the DataFrame:")
print(data.head())

# Print information about NaN values
print("\nNaN values in each column:")
print(data.isna().sum())

# Print data types of each column
print("\nData types of each column:")
print(data.dtypes)
