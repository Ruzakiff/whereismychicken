import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

def safe_to_datetime(x):
    try:
        return pd.to_datetime(x, utc=True)
    except ValueError:
        return pd.NaT

def convert_to_eastern(dt):
    if pd.isnull(dt):
        return dt
    eastern = pytz.timezone('US/Eastern')
    return dt.tz_convert(eastern)

# Load the data
data = pd.read_json('merged_chicken_data.json')

# Convert timestamp columns to datetime
datetime_columns = ['timestamp', 'start_time', 'actual_end_time', 'expected_end_time', 'new_expected_end_time', 'estimated_start_time']
for col in datetime_columns:
    if col in data.columns:
        data[col] = data[col].apply(safe_to_datetime)
        data[col] = data[col].apply(convert_to_eastern)

# Remove duplicates
data = data.drop_duplicates()

# Filter out entries before Oct 3, 10 AM EST
cutoff_time = pd.Timestamp('2024-10-03 10:00:00', tz='US/Eastern')
data = data[data['timestamp'] >= cutoff_time]

# Sort the data by oven and timestamp
data = data.sort_values(['oven', 'timestamp'])

# Initialize lists to store cooking sessions
sessions = []

# Iterate through each oven
for oven in data['oven'].unique():
    oven_data = data[data['oven'] == oven]
    current_session = None
    
    for _, row in oven_data.iterrows():
        if row['action'] == 'start_cooking':
            if current_session is not None:
                sessions.append(current_session)
            current_session = {
                'oven': oven,
                'start_time': row['timestamp'],
                'chickens': row['chickens'],
                'estimated_end_time': row['timestamp'] + timedelta(minutes=90)
            }
        elif row['action'] == 'adjust_cooking_time' and current_session is not None:
            if pd.notnull(row['new_time_left']):
                current_session['estimated_end_time'] = row['timestamp'] + timedelta(minutes=row['new_time_left'])
                current_session['start_time'] = current_session['estimated_end_time'] - timedelta(minutes=90)
        elif row['action'] == 'finish_cooking':
            if current_session is None:
                # If we have a finish time without a start time, estimate the start time
                current_session = {
                    'oven': oven,
                    'start_time': row['timestamp'] - timedelta(minutes=90),
                    'chickens': row['chickens'],
                }
            current_session['end_time'] = row['timestamp']
            current_session['actual_cooking_time'] = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
            sessions.append(current_session)
            current_session = None

# Create a DataFrame from the sessions
cooking_sessions = pd.DataFrame(sessions)

# Sort the dataframe
cooking_sessions = cooking_sessions.sort_values(['start_time', 'oven'])

# Add date column for grouping
cooking_sessions['date'] = cooking_sessions['start_time'].dt.date

# Group by date and oven
grouped_sessions = cooking_sessions.groupby(['date', 'oven'])

# Create a formatted output
output = []
for (date, oven), group in grouped_sessions:
    output.append(f"\nDate: {date}, Oven: {oven}")
    for _, session in group.iterrows():
        start = session['start_time'].strftime('%I:%M %p')
        end = session['end_time'].strftime('%I:%M %p') if pd.notnull(session['end_time']) else 'N/A'
        cooking_time = f"{session['actual_cooking_time']:.2f}" if 'actual_cooking_time' in session and pd.notnull(session['actual_cooking_time']) else 'N/A'
        output.append(f"  {start} - {end}: {session['chickens']} chickens, {cooking_time} minutes")

# Print the formatted output
print("\n".join(output))

# Save the grouped sessions to a CSV file
cooking_sessions.to_csv('grouped_cooking_sessions.csv', index=False)
print("\nGrouped cooking sessions saved to 'grouped_cooking_sessions.csv'")

# Print some statistics
print("\nCooking Time Statistics (minutes):")
print(cooking_sessions['actual_cooking_time'].describe())

print("\nCooking Sessions by Oven:")
print(cooking_sessions['oven'].value_counts().sort_index())

print("\nDate Range of Cooking Sessions:")
print(f"Start: {cooking_sessions['start_time'].min()}")
print(f"End: {cooking_sessions['end_time'].max()}")

print("\nTotal number of sessions:", len(cooking_sessions))
