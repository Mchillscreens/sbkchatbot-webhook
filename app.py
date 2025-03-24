from flask import Flask, request, jsonify
import os
import datetime
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
SERVICE_ACCOUNT_FILE = '/etc/secrets/breezy-calendar-interation-dab07558a5f0.json'
CALENDAR_ID = 'c_39dbf363c487045db93009e4f1bcaf7209d9c6f18c820a09e4992adbd22b49e9@group.calendar.google.com'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

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

def find_open_slots(date, slot_duration_minutes=60):
    work_start = datetime.datetime.combine(date, datetime.time(9, 0))  # 9 AM
    work_end = datetime.datetime.combine(date, datetime.time(17, 0))   # 5 PM

    events = get_events(work_start, work_end)

    busy_times = []
    for event in events:
        event_start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
        event_end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
        busy_times.append((event_start, event_end))

    free_times = []
    current_start = work_start

    for busy_start, busy_end in sorted(busy_times):
        if current_start < busy_start:
            free_times.append((current_start, busy_start))
        current_start = max(current_start, busy_end)

    if current_start < work_end:
        free_times.append((current_start, work_end))

    available_slots = []
    for free_start, free_end in free_times:
        slot_start = free_start
        while slot_start + datetime.timedelta(minutes=slot_duration_minutes) <= free_end:
            slot_end = slot_start + datetime.timedelta(minutes=slot_duration_minutes)
            available_slots.append({
                'start': slot_start.isoformat(),
                'end': slot_end.isoformat()
            })
            slot_start = slot_end

    print(f"DEBUG: Found {len(available_slots)} slots on {date} (min {slot_duration_minutes} mins)")
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
    print("📦 Raw Request:", data)

    if data is None:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["❗ Error: No JSON data received."]}}
                ]
            }
        }), 200

    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    appointment_date_str = data.get("sessionInfo", {}).get("parameters", {}).get("appointment-date")

    print(f"🖼️ screens_needed: {screens_needed}")
    print(f"📅 appointment_date_str: {appointment_date_str}")

    if not screens_needed:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["How many screens do you need serviced?"]}}
                ]
            }
        }), 200

    if not appointment_date_str:
        appointment_date_str = datetime.date.today().isoformat()

    appointment_date = datetime.datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    slots = find_open_slots(appointment_date)

    booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

    if not slots:
        next_date = None
        next_slots = []

        for days_ahead in range(1, 15):
            new_date = appointment_date + datetime.timedelta(days=days_ahead)
            potential_slots = find_open_slots(new_date)

            if potential_slots:
                next_date = new_date
                next_slots = potential_slots
                break

        if next_date:
            suggested_slots = []
            for slot in next_slots[:3]:
                start_time = slot['start'][11:16]
                suggested_slots.append(f"{next_date.strftime('%A, %B %d')} at {start_time}")

            chips = {
                "richContent": [
                    [
                        {
                            "type": "chips",
                            "options": [
                                {"text": slot, "link": booking_link} for slot in suggested_slots
                            ] + [
                                {"text": "See Full Booking Calendar", "link": booking_link}
                            ]
                        }
                    ]
                ]
            }

            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [f"❌ No times available on {appointment_date.strftime('%A, %B %d')}"]}},
                        {"text": {"text": [f"✅ Next openings on {next_date.strftime('%A, %B %d')}. Pick a time:"]}},
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
                                {"text": "See Full Booking Calendar", "link": booking_link}
                            ]
                        }
                    ]
                ]
            }

            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [f"❌ No times on {appointment_date.strftime('%A, %B %d')} or in the next 2 weeks."]}},
                        {"payload": chips}
                    ]
                }
            }), 200

    print(f"✅ Found {len(slots)} slots on {appointment_date_str}")

    formatted_slots = []
    for slot in slots:
        start_time = slot['start'][11:16]
        formatted_slots.append(f"{appointment_date.strftime('%A, %B %d')} at {start_time}")

    first_slot = formatted_slots[0]
    next_slots = formatted_slots[1:4]

    first_slot_message = f"✅ We have an opening for {first_slot}! Does this time work, or would you like to see more options?"

    chips = {
        "richContent": [
            [
                {
                    "type": "chips",
                    "options": [
                        {"text": slot, "link": booking_link} for slot in next_slots
                    ] + [
                        {"text": "See Full Booking Calendar", "link": booking_link}
                    ]
                }
            ]
        ]
    }

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [first_slot_message]}},
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
