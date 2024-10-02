from flask import Flask, jsonify, request, render_template_string
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import random
import json
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)

# Global variables
sams_club_opening_time = None
eastern_tz = pytz.timezone('US/Eastern')
total_ovens = 4
working_ovens = 4
chickens_per_oven = 32
chicken_shelf_life = 4 * 60  # 4 hours in minutes
available_chickens = []
oven_cycle_time = 100  # minutes

OPENING_SCHEDULE = {
    0: (8, 0),   # Monday
    1: (8, 0),   # Tuesday
    2: (8, 0),   # Wednesday
    3: (8, 0),   # Thursday
    4: (8, 0),   # Friday
    5: (8, 0),   # Saturday
    6: (10, 0),  # Sunday
}

# S3 configuration
S3_BUCKET = 'your-s3-bucket-name'
S3_KEY = 'chicken_data.json'

# Initialize S3 client
s3 = boto3.client('s3')

def get_sams_club_opening_time():
    global sams_club_opening_time, working_ovens
    now = datetime.now(eastern_tz)
    weekday = now.weekday()
    opening_hour, opening_minute = OPENING_SCHEDULE[weekday]
    todays_opening = now.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
    
    if now < todays_opening:
        sams_club_opening_time = todays_opening
    else:
        next_day = now + timedelta(days=1)
        next_weekday = next_day.weekday()
        next_opening_hour, next_opening_minute = OPENING_SCHEDULE[next_weekday]
        sams_club_opening_time = next_day.replace(hour=next_opening_hour, minute=next_opening_minute, second=0, microsecond=0)
    
    # Randomly decide if an oven is out of order
    working_ovens = 3 if random.random() < 0.2 else 4
    
    print(f"Next opening time: {sams_club_opening_time}, Working ovens: {working_ovens}")

def cook_chickens(time, quantity):
    global available_chickens
    available_chickens.append((time, quantity))

def remove_expired_chickens(current_time):
    global available_chickens
    available_chickens = [(time, quantity) for time, quantity in available_chickens 
                          if (current_time - time).total_seconds() / 60 < chicken_shelf_life]

@app.route('/status', methods=['GET'])
def get_status():
    now = datetime.now(eastern_tz)
    if sams_club_opening_time is None or now.date() > sams_club_opening_time.date():
        get_sams_club_opening_time()
    
    weekday = now.weekday()
    opening_hour, opening_minute = OPENING_SCHEDULE[weekday]
    todays_opening = now.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
    
    remove_expired_chickens(now)
    
    if now >= todays_opening:
        minutes_since_opening = int((now - todays_opening).total_seconds() // 60)
        
        # At opening time, one oven is already done and another starts
        if minutes_since_opening == 0:
            cook_chickens(now, chickens_per_oven)  # One oven already done
            cook_chickens(now - timedelta(minutes=oven_cycle_time), chickens_per_oven)  # Another oven starting
        
        # Cook chickens in cycles throughout the day
        elif minutes_since_opening % oven_cycle_time == 0 and now.hour < 17:
            cook_chickens(now, chickens_per_oven)
        
        # Cook chickens around 5 PM
        elif now.hour == 17 and now.minute == 0:
            cook_chickens(now, 2 * chickens_per_oven)  # Last two ovens come out
        
        is_available = len(available_chickens) > 0
    else:
        minutes_since_opening = int((now - sams_club_opening_time).total_seconds() // 60)
        is_available = False

    total_available_chickens = sum(quantity for _, quantity in available_chickens)

    return jsonify({
        'sams_club_opening_time': sams_club_opening_time.isoformat() if sams_club_opening_time else None,
        'current_time': now.isoformat(),
        'minutes_since_opening': minutes_since_opening,
        'is_available': is_available,
        'working_ovens': working_ovens,
        'available_chickens': total_available_chickens
    })

@app.route('/log_data', methods=['POST'])
def log_data():
    data = request.json
    required_fields = [
        'timestamp',
        'batch_start_time',
        'batch_end_time',
        'chickens_cooked',
        'chickens_sold',
        'working_ovens',
        'oven_number',
        'special_event',
        'weather',
        'temperature',
        'unexpected_issues',
        'staff_on_duty'
    ]
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Add some automatic fields
    batch_start = datetime.fromisoformat(data['batch_start_time'])
    batch_end = datetime.fromisoformat(data['batch_end_time'])
    data['cooking_duration'] = (batch_end - batch_start).total_seconds() / 60
    data['day_of_week'] = batch_start.weekday()
    data['time_of_day'] = batch_start.strftime('%H:%M')
    data['is_weekend'] = batch_start.weekday() >= 5
    
    # Load existing data from S3
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        existing_data = json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data = []
        else:
            return jsonify({'error': 'Failed to retrieve existing data'}), 500
    
    # Append new data
    existing_data.append(data)
    
    # Save updated data to S3
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=json.dumps(existing_data, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
    except ClientError:
        return jsonify({'error': 'Failed to save data'}), 500
    
    return jsonify({'message': 'Data logged successfully'}), 200

@app.route('/input', methods=['GET'])
def input_form():
    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Log Chicken Data</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; }
            input, select { width: 100%; padding: 8px; margin: 5px 0 15px; }
            button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <h2>Log Chicken Data</h2>
        <form id="chickenForm">
            <label for="batch_start_time">Batch Start Time:</label>
            <input type="datetime-local" id="batch_start_time" required>
            
            <label for="batch_end_time">Batch End Time:</label>
            <input type="datetime-local" id="batch_end_time" required>
            
            <label for="chickens_cooked">Chickens Cooked:</label>
            <input type="number" id="chickens_cooked" required>
            
            <label for="chickens_sold">Chickens Sold:</label>
            <input type="number" id="chickens_sold" required>
            
            <label for="working_ovens">Working Ovens:</label>
            <input type="number" id="working_ovens" min="1" max="4" required>
            
            <label for="oven_number">Oven Number:</label>
            <input type="number" id="oven_number" min="1" max="4" required>
            
            <label for="special_event">Special Event:</label>
            <input type="text" id="special_event">
            
            <label for="weather">Weather:</label>
            <select id="weather" required>
                <option value="sunny">Sunny</option>
                <option value="cloudy">Cloudy</option>
                <option value="rainy">Rainy</option>
                <option value="snowy">Snowy</option>
            </select>
            
            <label for="temperature">Temperature (°F):</label>
            <input type="number" id="temperature" required>
            
            <label for="unexpected_issues">Unexpected Issues:</label>
            <input type="text" id="unexpected_issues">
            
            <label for="staff_on_duty">Staff on Duty:</label>
            <input type="number" id="staff_on_duty" required>
            
            <button type="submit">Submit</button>
        </form>
        
        <script>
            document.getElementById('chickenForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                var data = {
                    timestamp: new Date().toISOString(),
                    batch_start_time: document.getElementById('batch_start_time').value,
                    batch_end_time: document.getElementById('batch_end_time').value,
                    chickens_cooked: parseInt(document.getElementById('chickens_cooked').value),
                    chickens_sold: parseInt(document.getElementById('chickens_sold').value),
                    working_ovens: parseInt(document.getElementById('working_ovens').value),
                    oven_number: parseInt(document.getElementById('oven_number').value),
                    special_event: document.getElementById('special_event').value || null,
                    weather: document.getElementById('weather').value,
                    temperature: parseInt(document.getElementById('temperature').value),
                    unexpected_issues: document.getElementById('unexpected_issues').value || null,
                    staff_on_duty: parseInt(document.getElementById('staff_on_duty').value)
                };
                
                fetch('/log_data', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                })
                .then(response => response.json())
                .then(data => {
                    alert('Data logged successfully');
                    document.getElementById('chickenForm').reset();
                })
                .catch((error) => {
                    alert('Error logging data: ' + error);
                });
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

# Initialize the scheduler
scheduler = BackgroundScheduler(timezone=eastern_tz)
scheduler.add_job(get_sams_club_opening_time, 'cron', hour=0, minute=0)
scheduler.start()

if __name__ == '__main__':
    get_sams_club_opening_time()  # Initialize the opening time
    app.run(debug=True)
