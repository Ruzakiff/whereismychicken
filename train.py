import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load the cleaned data
data = pd.read_json('cleaned_chicken_data.json')

# Filter out rows with missing end times
data = data.dropna(subset=['actual_end_time'])

# Function to get the most common finish time for each oven and day of week
def get_common_finish_times():
    finish_times = {}
    for oven in range(1, 5):
        finish_times[oven] = {}
        for day in range(7):
            oven_day_data = data[(data['oven'] == oven) & (data['day_of_week'] == day)]
            if not oven_day_data.empty:
                common_time = oven_day_data['actual_end_time'].dt.hour.mode().iloc[0]
                finish_times[oven][day] = common_time
            else:
                finish_times[oven][day] = None
    return finish_times

common_finish_times = get_common_finish_times()

def predict_time_until_ready(oven, current_time):
    day_of_week = current_time.weekday()
    if oven not in common_finish_times or day_of_week not in common_finish_times[oven] or common_finish_times[oven][day_of_week] is None:
        return "No data available for this oven on this day"

    common_finish_hour = common_finish_times[oven][day_of_week]
    predicted_finish_time = current_time.replace(hour=common_finish_hour, minute=0, second=0, microsecond=0)
    
    # If the predicted finish time is in the past, assume it's for the next day
    if predicted_finish_time <= current_time:
        predicted_finish_time += timedelta(days=1)
    
    time_until_ready = (predicted_finish_time - current_time).total_seconds() / 60
    return round(time_until_ready)

# Function to get predictions for all ovens
def get_todays_predictions():
    current_time = datetime.now()
    predictions = {}
    for oven in range(1, 5):
        time_until_ready = predict_time_until_ready(oven, current_time)
        if isinstance(time_until_ready, int):
            predictions[f'Oven {oven}'] = f"Ready in: {time_until_ready} min"
        else:
            predictions[f'Oven {oven}'] = time_until_ready
    return predictions

# Example usage for today's predictions
today_predictions = get_todays_predictions()
print("Today's predictions:", today_predictions)

# Function to get prediction for a specific oven
def get_oven_prediction(oven):
    current_time = datetime.now()
    time_until_ready = predict_time_until_ready(oven, current_time)
    if isinstance(time_until_ready, int):
        return f"Ready in: {time_until_ready} min"
    else:
        return time_until_ready

# Example usage for a specific oven
print("\nPrediction for Oven 1:")
print(get_oven_prediction(oven=1))

# Print common finish times for analysis
print("\nCommon finish times for each oven and day:")
days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
for oven in common_finish_times:
    print(f"\nOven {oven}:")
    for day in range(7):
        time = common_finish_times[oven][day]
        print(f"  {days[day]}: {time if time is not None else 'No data'}")
