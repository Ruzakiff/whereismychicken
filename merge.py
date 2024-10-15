import json
from datetime import datetime

def merge_chicken_data(file1, file2):
    # Read data from both files
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    # Combine the data
    merged_data = data1 + data2

    # Sort the merged data by timestamp
    merged_data.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')))

    # Remove duplicates based on timestamp
    seen = set()
    unique_data = []
    for item in merged_data:
        if item['timestamp'] not in seen:
            seen.add(item['timestamp'])
            unique_data.append(item)

    # Write the merged and sorted data to a new file
    with open('merged_chicken_data.json', 'w') as outfile:
        json.dump(unique_data, outfile, indent=2)

    print("Merged data has been written to 'merged_chicken_data.json'")

# Call the function with the two input files
merge_chicken_data('chicken_dataog.json', 'chicken_data(1).json')
