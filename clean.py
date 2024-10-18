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

# Identify and remove duplicates based on 'oven' and 'timestamp'
duplicates = data[data.duplicated(subset=['oven', 'timestamp'], keep=False)]
print("Duplicates found:")
print(duplicates)
print(f"\nNumber of duplicates: {len(duplicates)}")

# Remove duplicates, keeping the first occurrence
data_no_duplicates = data.drop_duplicates(subset=['oven', 'timestamp'], keep='first')

# Filter out entries before Oct 3, 10 AM EST
cutoff_time = pd.Timestamp('2024-10-03 10:00:00', tz='US/Eastern')
data_filtered = data_no_duplicates[data_no_duplicates['timestamp'] >= cutoff_time]

print(f"\nRows removed due to early timestamp: {len(data_no_duplicates) - len(data_filtered)}")

# Sort the data by oven and timestamp
data_filtered = data_filtered.sort_values(['oven', 'timestamp'])

# Save the new dataset
data_filtered.to_json('cleaned_chicken_data.json', date_format='iso')
print("\nCleaned data saved to 'cleaned_chicken_data.json'")

# Print summary of changes
print(f"\nOriginal dataset size: {len(data)}")
print(f"Dataset size after removing duplicates: {len(data_no_duplicates)}")
print(f"Final dataset size after filtering early entries: {len(data_filtered)}")

# Initialize lists to store cooking sessions
sessions = []

# Iterate through each oven
for oven in data_filtered['oven'].unique():
    oven_data = data_filtered[data_filtered['oven'] == oven].sort_values('timestamp')
    current_session = None
    
    for _, row in oven_data.iterrows():
        if row['action'] == 'start_cooking':
            if current_session is not None:
                sessions.append(current_session)
            current_session = {
                'oven': oven,
                'start_time': row['timestamp'],
                'chickens': row['chickens'],
                'expected_end_time': row['expected_end_time'],
                'leftovers': None,
                'leftovers_time': None
            }
        elif row['action'] == 'adjust_cooking_time' and current_session is not None:
            if pd.notnull(row['new_expected_end_time']):
                current_session['expected_end_time'] = row['new_expected_end_time']
        elif row['action'] == 'finish_cooking':
            if current_session is None:
                # If we have a finish time without a start time, estimate the start time
                current_session = {
                    'oven': oven,
                    'start_time': row['timestamp'] - timedelta(minutes=90),
                    'chickens': row['chickens'],
                    'expected_end_time': row['timestamp'],  # Assume expected = actual if we don't have start data
                    'leftovers': None,
                    'leftovers_time': None
                }
            current_session['end_time'] = row['timestamp']
            current_session['actual_cooking_time'] = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
            
            # Adjust start time if cooking duration is less than 60 minutes
            if current_session['actual_cooking_time'] < 60:
                imputed_duration = np.random.uniform(90, 100)  # Random duration between 90-100 minutes
                current_session['start_time'] = current_session['end_time'] - timedelta(minutes=imputed_duration)
                current_session['actual_cooking_time'] = imputed_duration
            
            current_session['time_difference'] = (current_session['end_time'] - current_session['expected_end_time']).total_seconds() / 60
        elif row['action'] == 'post_rush':
            if current_session is not None:
                current_session['leftovers'] = row['chickens_left']
                current_session['leftovers_time'] = row['timestamp']
                sessions.append(current_session)
                current_session = None

    # Append the last session if it exists
    if current_session is not None:
        sessions.append(current_session)

# Create a DataFrame from the sessions
cooking_sessions = pd.DataFrame(sessions)

# Calculate time between end_time and leftovers_time
cooking_sessions['time_to_leftovers'] = (cooking_sessions['leftovers_time'] - cooking_sessions['end_time']).dt.total_seconds() / 60

# Add new analysis for leftovers
print("\nLeftovers Analysis:")
sessions_with_leftovers = cooking_sessions[cooking_sessions['leftovers'].notnull()]
print(f"Total sessions with leftovers: {len(sessions_with_leftovers)}")

print("\nLeftovers statistics:")
print(sessions_with_leftovers['leftovers'].describe())

print("\nTime to log leftovers statistics (minutes):")
print(sessions_with_leftovers['time_to_leftovers'].describe())

print("\nSample of sessions with leftovers:")
print(sessions_with_leftovers[['oven', 'end_time', 'chickens', 'leftovers', 'leftovers_time', 'time_to_leftovers']].head())

# Update the formatted output to include leftovers information
output = []
for (date, oven), group in cooking_sessions.groupby([cooking_sessions['start_time'].dt.date, 'oven']):
    output.append(f"\nDate: {date}, Oven: {oven}")
    for _, session in group.iterrows():
        start = session['start_time'].strftime('%I:%M %p')
        end = session['end_time'].strftime('%I:%M %p') if pd.notnull(session['end_time']) else 'N/A'
        cooking_time = f"{session['actual_cooking_time']:.2f}" if pd.notnull(session['actual_cooking_time']) else 'N/A'
        time_diff = f"{session['time_difference']:.2f}" if pd.notnull(session['time_difference']) else 'N/A'
        leftovers = f"{session['leftovers']}" if pd.notnull(session['leftovers']) else 'N/A'
        leftovers_time = session['leftovers_time'].strftime('%I:%M %p') if pd.notnull(session['leftovers_time']) else 'N/A'
        time_to_leftovers = f"{session['time_to_leftovers']:.2f}" if pd.notnull(session['time_to_leftovers']) else 'N/A'
        session_info = (f"  {start} - {end}: {session['chickens']} chickens, {cooking_time} minutes, "
                        f"Difference: {time_diff} minutes, Leftovers: {leftovers} at {leftovers_time} "
                        f"({time_to_leftovers} minutes after finish)")
        if pd.isnull(session['end_time']):
            session_info += " (No finish time)"
        output.append(session_info)

# Print the updated formatted output
print("\nCooking Sessions (including detailed leftovers information):")
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

# Add statistics for time difference
print("\nTime Difference Statistics (minutes):")
print(cooking_sessions['time_difference'].describe())

