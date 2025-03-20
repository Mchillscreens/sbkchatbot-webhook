from flask import Flask, request, jsonify
import os
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================
# Flask App Setup
# ==========================
app = Flask(__name__)

# ==========================
# Google Calendar API Setup
# ==========================
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'breezy-calendar-interation-dab07558a5f0.json'  # <-- CHANGE THIS
CALENDAR_ID = 'c_39dbf363c487045db93009e4f1bcaf7209d9c6f18c820a09e4992adbd22b49e9@group.calendar.google.com'    # <-- CHANGE THIS

# Load credentials from your Service Account JSON key file
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Build the Google Calendar API service
service = build('calendar', 'v3', credentials=credentials)

# ==========================
# Helper Functions
# ==========================

def get_events(start_time, end_time):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return events

def find_open_slots(date):
    # Define your working hours here
    work_start = datetime.datetime.combine(date, datetime.time(9, 0))  # 9 AM
    work_end = datetime.datetime.combine(date, datetime.time(17, 0))   # 5 PM

    events = get_events(work_start, work_end)

    slots = []
    current_time = work_start

    for event in events:
        event_start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
        event_end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))

        if current_time < event_start:
            slots.append((current_time, event_start))

        current_time = max(current_time, event_end)

    if current_time < work_end:
        slots.append((current_time, work_end))

    available_slots = []
    for start, end in slots:
        available_slots.append({
            'start': start.isoformat(),
            'end': end.isoformat()
        })

    return available_slots

# ==========================
# Routes
# ==========================

@app.route("/", methods=["GET"])
def home():
    return "✅ Webhook is alive!"

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("✅ Webhook called at /get_availability")

    data = request.get_json(silent=True)

    print("📦 Raw Request (request.data):", request.data)
    print("📦 Parsed JSON (data):", data)

    if data is None:
        print("❗ No JSON data received.")
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "❗ Error: No valid JSON data received."
                    ]}}
                ]
            }
        }), 200

    # Step 1: Get number of screens requested
    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    print(f"🖼️ screens_needed: {screens_needed}")

    if not screens_needed:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "How many screens do you need serviced?"
                    ]}}
                ]
            }
        }), 200

    # Step 2: Get the requested appointment date
    appointment_date_str = data.get("sessionInfo", {}).get("parameters", {}).get("appointment-date")

    if not appointment_date_str:
        appointment_date_str = datetime.date.today().isoformat()  # Default to today if no date

    appointment_date = datetime.datetime.strptime(appointment_date_str, '%Y-%m-%d').date()

    # Step 3: Find available slots on the requested date
    slots = find_open_slots(appointment_date)

    # Step 4: If no slots, find next available date
    if not slots:
        print(f"❌ No slots found on {appointment_date_str}.")

        next_date = None
        next_slots = []
        for days_ahead in range(1, 15):  # Look 14 days ahead
            new_date = appointment_date + datetime.timedelta(days=days_ahead)
            potential_slots = find_open_slots(new_date)

            if potential_slots:
                next_date = new_date
                next_slots = potential_slots
                print(f"✅ Found next available date: {next_date}")
                break

        booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

        if next_date:
            suggested_slots = []
            for slot in next_slots[:3]:  # Offer top 3 slots
                start_time = slot['start'][11:16]
                suggested_slots.append(f"{next_date.strftime('%A, %B %d')} at {start_time}")

            chips = {
                "richContent": [
                    [
                        {
                            "type": "chips",
                            "options": [
                                {
                                    "text": slot,
                                    "link": booking_link
                                } for slot in suggested_slots
                            ]
                        },
                        {
                            "type": "chips",
                            "options": [
                                {
                                    "text": "See Full Booking Calendar",
                                    "link": booking_link
                                }
                            ]
                        }
                    ]
                ]
            }

            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [
                            f"❌ Sorry, no times available on {appointment_date.strftime('%A, %B %d')}."
                        ]}},
                        {"text": {"text": [
                            f"✅ But good news! We have openings on {next_date.strftime('%A, %B %d')}. Pick a time below to book:"
                        ]}},
                        {"text": {"text": [
                            "⚠️ Heads up! If you book through the site, Breezy won’t be able to help from there—but we’ll take care of you once you're booked!"
                        ]}},
                        {"payload": chips}
                    ]
                }
            }), 200

        else:
            chips = {
                "richContent": [
                    [
                        {
                            "type": "chips",
                            "options": [
                                {
                                    "text": "See Full Booking Calendar",
                                    "link": booking_link
                                }
                            ]
                        }
                    ]
                ]
            }

            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [
                            f"❌ Sorry, no available times on {appointment_date.strftime('%A, %B %d')} or in the next 2 weeks."
                        ]}},
                        {"text": {"text": [
                            "You can check out our full booking calendar below:"
                        ]}},
                        {"text": {"text": [
                            "⚠️ Heads up! If you book through the site, Breezy won’t be able to help from there—but we’ll take care of you once you're booked!"
                        ]}},
                        {"payload": chips}
                    ]
                }
            }), 200

    # Step 5: If slots are available on the requested date
    print(f"✅ Found {len(slots)} slots on {appointment_date_str}.")

    time_slots = []
    for slot in slots[:3]:
        start_time = slot['start'][11:16]
        time_slots.append(f"{appointment_date.strftime('%A, %B %d')} at {start_time}")

    chips = {
        "richContent": [
            [
                {
                    "type": "chips",
                    "options": [
                        {
                            "text": slot,
                            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
                        } for slot in time_slots
                    ]
                },
                {
                    "type": "chips",
                    "options": [
                        {
                            "text": "See Full Booking Calendar",
                            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
                        }
                    ]
                }
            ]
        ]
    }

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have openings for {screens_needed} screens! Pick a time below to book on {appointment_date.strftime('%A, %B %d')}!"
                ]}},
                {"payload": chips}
            ]
        }
    }), 200

# ==========================
# Run the Flask App
# ==========================
if __name__ == "__main__":
    print("✅ Starting Flask App")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
