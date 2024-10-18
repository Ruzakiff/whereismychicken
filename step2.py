import json
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load the JSON data
with open('cleaned_chicken_data.json', 'r') as f:
    data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(data)

# Convert timestamp strings to datetime objects
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Function to calculate cooking duration
def calculate_cooking_duration(row):
    if row['action'] == 'start_cooking':
        start_time = row['timestamp']
        finish_time = df[(df['timestamp'] > start_time) & (df['action'] == 'finish_cooking')]['timestamp'].min()
        if pd.notnull(finish_time):
            return (finish_time - start_time).total_seconds() / 60  # Duration in minutes
    return None

# Calculate cooking durations
df['cooking_duration'] = df.apply(calculate_cooking_duration, axis=1)

# Function to check for start times without finish times
def check_missing_finish_times(df):
    start_times = df[df['action'] == 'start_cooking']['timestamp']
    missing_finish = []
    for start_time in start_times:
        finish_time = df[(df['timestamp'] > start_time) & (df['action'] == 'finish_cooking')]['timestamp'].min()
        if pd.isnull(finish_time):
            missing_finish.append(start_time)
    return missing_finish

# Highlight start times without finish times
missing_finish_times = check_missing_finish_times(df)
if missing_finish_times:
    print("\nWarning: The following start times have no corresponding finish time:")
    for time in missing_finish_times:
        print(f"  - {time}")
else:
    print("\nAll start times have corresponding finish times.")

# Calculate average cooking duration
average_duration = df['cooking_duration'].mean()
median_duration = df['cooking_duration'].median()

# Function to estimate missing start times
def estimate_start_time(row):
    if row['action'] == 'finish_cooking':
        if pd.notnull(row['cooking_duration']) and row['cooking_duration'] < 60:
            # For durations less than 60 minutes, impute start time between 90-100 minutes before finish
            imputed_duration = np.random.uniform(90, 100)
            estimated_start = row['timestamp'] - timedelta(minutes=imputed_duration)
            return estimated_start, True
        else:
            # For other cases, use the average duration as before
            estimated_start = row['timestamp'] - timedelta(minutes=average_duration)
            return estimated_start, True
    return row['timestamp'], False

# Estimate missing start times and add flags
df['imputed_start_time'], df['is_imputed'] = zip(*df.apply(estimate_start_time, axis=1))

# Recalculate cooking durations after imputation
def recalculate_cooking_duration(row):
    if row['action'] == 'finish_cooking':
        if row['is_imputed']:
            return (row['timestamp'] - row['imputed_start_time']).total_seconds() / 60
        else:
            return row['cooking_duration']
    return row['cooking_duration']

df['cooking_duration'] = df.apply(recalculate_cooking_duration, axis=1)

# Correct invalid data if columns exist
if 'batch_size' in df.columns:
    df['batch_size'] = df['batch_size'].clip(lower=0)
if 'leftovers' in df.columns:
    df['leftovers'] = df['leftovers'].clip(lower=0)

# Save the processed data as JSON
df.to_json('processed_chicken_data.json', orient='records', date_format='iso')

print(f"Average cooking duration: {average_duration:.2f} minutes")
print(f"Median cooking duration: {median_duration:.2f} minutes")
print("Processed data saved to 'processed_chicken_data.json'")

# Print column names for debugging
print("\nColumns in the DataFrame:")
print(df.columns.tolist())
