import pandas as pd
import numpy as np
from datetime import timedelta

# Load the cleaned data
cooking_sessions = pd.read_csv('grouped_cooking_sessions.csv')

# Convert datetime columns
datetime_columns = ['start_time', 'expected_end_time', 'end_time']
for col in datetime_columns:
    cooking_sessions[col] = pd.to_datetime(cooking_sessions[col])

# 1. Calculate New Features

# Cooking Duration
cooking_sessions['cooking_duration'] = (cooking_sessions['end_time'] - cooking_sessions['start_time']).dt.total_seconds() / 60

# Time Since Last Batch
cooking_sessions = cooking_sessions.sort_values(['oven', 'start_time'])
cooking_sessions['time_since_last_batch'] = cooking_sessions.groupby('oven')['start_time'].diff().dt.total_seconds() / 60

# Daily Patterns
cooking_sessions['hour'] = cooking_sessions['start_time'].dt.hour
cooking_sessions['day_of_week'] = cooking_sessions['start_time'].dt.dayofweek

# Cyclical encoding for hour and day of week
cooking_sessions['hour_sin'] = np.sin(cooking_sessions['hour'] * (2 * np.pi / 24))
cooking_sessions['hour_cos'] = np.cos(cooking_sessions['hour'] * (2 * np.pi / 24))
cooking_sessions['day_of_week_sin'] = np.sin(cooking_sessions['day_of_week'] * (2 * np.pi / 7))
cooking_sessions['day_of_week_cos'] = np.cos(cooking_sessions['day_of_week'] * (2 * np.pi / 7))

# 2. Impute Additional Features Based on Batch Size

# Check if 'leftovers' column exists
if 'leftovers' in cooking_sessions.columns:
    # Ensure 'leftovers' and 'chickens' are numeric
    cooking_sessions['leftovers'] = pd.to_numeric(cooking_sessions['leftovers'], errors='coerce')
    cooking_sessions['chickens'] = pd.to_numeric(cooking_sessions['chickens'], errors='coerce')
    
    # Calculate leftovers ratio
    cooking_sessions['leftovers_ratio'] = cooking_sessions['leftovers'] / cooking_sessions['chickens']
else:
    print("Note: 'leftovers' column not found. Skipping leftovers ratio calculation.")

# Print summary of new features
print("\nSummary of new features:")
new_features = ['cooking_duration', 'time_since_last_batch', 'hour', 'day_of_week', 
                'hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos']
if 'leftovers_ratio' in cooking_sessions.columns:
    new_features.append('leftovers_ratio')

print(cooking_sessions[new_features].describe())

# Save the updated dataset
cooking_sessions.to_csv('cooking_sessions_engineered.csv', index=False)
print("\nUpdated dataset with engineered features saved to 'cooking_sessions_engineered.csv'")

# Additional analysis: Check for correlations between new features and existing ones
print("\nCorrelations between new features and batch size:")
correlations = cooking_sessions[['chickens'] + new_features].corr()['chickens'].sort_values(ascending=False)
print(correlations)

# Visualize the distribution of cooking durations
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.hist(cooking_sessions['cooking_duration'].dropna(), bins=30)
plt.title('Distribution of Cooking Durations')
plt.xlabel('Cooking Duration (minutes)')
plt.ylabel('Frequency')
plt.savefig('cooking_duration_distribution.png')
plt.close()

print("\nA histogram of cooking durations has been saved as 'cooking_duration_distribution.png'")

# Visualize the relationship between batch size and cooking duration
plt.figure(figsize=(10, 6))
plt.scatter(cooking_sessions['chickens'], cooking_sessions['cooking_duration'])
plt.title('Batch Size vs Cooking Duration')
plt.xlabel('Number of Chickens')
plt.ylabel('Cooking Duration (minutes)')
plt.savefig('batch_size_vs_cooking_duration.png')
plt.close()

print("\nA scatter plot of batch size vs cooking duration has been saved as 'batch_size_vs_cooking_duration.png'")
