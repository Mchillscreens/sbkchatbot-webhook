import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, time
import pytz
import google.auth
from googleapiclient.discovery import build
from google.oauth2 import service_account

app = Flask(__name__)

# Load Google credentials
SERVICE_ACCOUNT_FILE = 'breezy-calendar-interation-dab07558a5f0.json'
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CALENDAR_ID = 'c_39dbf363c487045db93009e4f1bcaf7209d9c6f18c820a09e4992adbd22b49e9@group.calendar.google.com'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Timezone and business rules
pst = pytz.timezone("America/Los_Angeles")
business_start = time(8, 0)
business_end = time(17, 0)

def get_busy_times():
    service = build('calendar', 'v3', credentials=credentials)
    now = datetime.now(pst)
    future = now + timedelta(days=10)
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=future.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    busy_times = []
    for event in events:
        start = event['start'].get('dateTime')
        end = event['end'].get('dateTime')
        if start and end:
            start_dt = datetime.fromisoformat(start).astimezone(pst)
            end_dt = datetime.fromisoformat(end).astimezone(pst)
            busy_times.append((start_dt, end_dt))
    return busy_times

def generate_availability(busy_times):
    availability = []
    now = datetime.now(pst)
    current_day = now + timedelta(days=1)  # skip today

    while len(availability) < 5:
        if current_day.weekday() < 5:  # Mon–Fri only
            slot = pst.localize(datetime.combine(current_day.date(), business_start))
            end_dt = pst.localize(datetime.combine(current_day.date(), business_end))

            while slot < end_dt:
                slot_end = slot + timedelta(hours=1)
                if not any(start < slot_end and slot < end for start, end in busy_times):
                    if slot > now:
                        availability.append(slot.strftime("%A, %B %d at %H:%M"))
                slot += timedelta(hours=1)
        current_day += timedelta(days=1)

    return availability[:5]

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json()
    # Optional: check if user requested today
    now = datetime.now(pst)
    user_date = req.get("sessionInfo", {}).get("parameters", {}).get("date")
print("Incoming user_date:", user_date)
try:
    if user_date:
        parsed = datetime.fromisoformat(user_date.replace("Z", "+00:00")).astimezone(pst)
        if parsed.date() == now.date():
            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": ["Same-day appointments must be booked by phone. Please call our office at 760-248-8000."]}}
                    ]
                },
                "sessionInfo": {
                    "parameters": {
                        "booking_flow_completed": True
                    }
                }
            })
except Exception as e:
    print("Date parsing error:", str(e))


    busy_times = get_busy_times()
    available = generate_availability(busy_times)

    if not available:
        msg = "Sorry, no availability was found this week. Please try again later or call us at 760-248-8000."
    else:
        msg = f"Here's our next available time: {available[0]}. Would you like to book it?"

    return jsonify({
        "fulfillment_response": {
            "messages": [{"text": {"text": [msg]}}]
        },
        "sessionInfo": {
            "parameters": {
                "available_times": available,
                "booking_flow_completed": False
            }
        }
    })

if __name__ == '__main__':
    app.run(debug=True)
