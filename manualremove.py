import json
from datetime import datetime, timedelta

def parse_datetime(dt_string):
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.strptime(dt_string, '%I:%M %p')
        except ValueError:
            return None

def format_time(dt):
    if dt is None:
        return "Unknown"
    return dt.strftime('%I:%M %p')

def load_data(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def save_data(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=2)

def remove_specific_entry(data):
    removed_entries = []
    cleaned_data = []
    
    for i, entry in enumerate(data):
        if (entry['action'] == 'finish_cooking' and
            entry['oven'] == 1 and
            parse_datetime(entry['start_time']) == parse_datetime('05:46 PM') and
            parse_datetime(entry['actual_end_time']) == parse_datetime('05:46 PM')):
            removed_entries.append(entry)
        else:
            cleaned_data.append(entry)
    
    return cleaned_data, removed_entries

def main():
    input_file = 'merged_chicken_data.json'
    output_file = 'cleaned_chicken_data.json'
    
    data = load_data(input_file)
    cleaned_data, removed_entries = remove_specific_entry(data)
    
    save_data(cleaned_data, output_file)
    
    print(f"Original data entries: {len(data)}")
    print(f"Cleaned data entries: {len(cleaned_data)}")
    print(f"Removed entries: {len(removed_entries)}")
    
    if removed_entries:
        print("\nRemoved entries:")
        for entry in removed_entries:
            print(f"Oven: {entry['oven']}, "
                  f"Start Time: {entry['start_time']}, "
                  f"End Time: {entry['actual_end_time']}, "
                  f"Chickens: {entry['chickens']}")

if __name__ == "__main__":
    main()

