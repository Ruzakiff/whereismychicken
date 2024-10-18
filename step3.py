import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Load the data
cooking_sessions = pd.read_csv('grouped_cooking_sessions.csv')

# Convert datetime columns
datetime_columns = ['start_time', 'end_time']
for col in datetime_columns:
    if col in cooking_sessions.columns:
        cooking_sessions[col] = pd.to_datetime(cooking_sessions[col])

# Calculate time intervals between batches
cooking_sessions = cooking_sessions.sort_values(['oven', 'start_time'])
cooking_sessions['time_interval'] = cooking_sessions.groupby('oven')['start_time'].diff().dt.total_seconds() / 60

# Function to plot histogram
def plot_histogram(data, column, title):
    plt.figure(figsize=(10, 6))
    plt.hist(data[column].dropna(), bins=30)
    plt.title(title)
    plt.xlabel(column)
    plt.ylabel('Frequency')
    plt.savefig(f'{column}_histogram.png')
    plt.close()

# Plot histograms
columns_to_plot = ['actual_cooking_time', 'chickens', 'time_interval']
for column in columns_to_plot:
    if column in cooking_sessions.columns:
        plot_histogram(cooking_sessions, column, f'Distribution of {column.replace("_", " ").title()}')

# Function to remove outliers
def remove_outliers(df, column, z_threshold=3):
    df_clean = df.copy()
    if df_clean[column].dtype == 'object':
        df_clean[column] = pd.to_numeric(df_clean[column], errors='coerce')
    
    z_scores = np.abs(stats.zscore(df_clean[column].dropna()))
    mask = z_scores > z_threshold
    outliers = df_clean.loc[df_clean[column].notna()][mask]
    df_clean = df_clean.loc[~df_clean.index.isin(outliers.index)]
    return df_clean, outliers

# Remove outliers
columns_to_clean = ['actual_cooking_time', 'chickens', 'time_interval']
outliers_log = {}

for column in columns_to_clean:
    if column in cooking_sessions.columns:
        cooking_sessions, outliers = remove_outliers(cooking_sessions, column)
        outliers_log[column] = outliers

# Print summary of removed outliers
print("Summary of removed outliers:")
for column, outliers in outliers_log.items():
    print(f"{column}: {len(outliers)} outliers removed")
    print(outliers.describe())
    print("\n")

# Plot histograms after outlier removal
for column in columns_to_clean:
    if column in cooking_sessions.columns:
        plot_histogram(cooking_sessions, column, f'Distribution of {column} (After Outlier Removal)')

# Save cleaned data
cooking_sessions.to_csv('cleaned_cooking_sessions.csv', index=False)
print("Cleaned data saved to 'cleaned_cooking_sessions.csv'")

# Print summary statistics of cleaned data
print("\nSummary statistics of cleaned data:")
print(cooking_sessions[columns_to_clean].describe())

# Flag extreme values instead of removing them
def flag_extreme_values(df, column, z_threshold=3):
    df_flagged = df.copy()
    if df_flagged[column].dtype == 'object':
        df_flagged[column] = pd.to_numeric(df_flagged[column], errors='coerce')
    
    z_scores = np.abs(stats.zscore(df_flagged[column].dropna()))
    df_flagged[f'{column}_extreme'] = pd.Series(False, index=df_flagged.index)
    df_flagged.loc[df_flagged[column].notna(), f'{column}_extreme'] = z_scores > z_threshold
    return df_flagged

# Flag extreme values
for column in columns_to_clean:
    if column in cooking_sessions.columns:
        cooking_sessions = flag_extreme_values(cooking_sessions, column)

# Print summary of flagged extreme values
print("\nSummary of flagged extreme values:")
for column in columns_to_clean:
    if column in cooking_sessions.columns:
        extreme_count = cooking_sessions[f'{column}_extreme'].sum()
        print(f"{column}: {extreme_count} extreme values flagged")

# Save data with flagged extreme values
cooking_sessions.to_csv('cooking_sessions_with_flags.csv', index=False)
print("Data with flagged extreme values saved to 'cooking_sessions_with_flags.csv'")
