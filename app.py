from flask import Flask, request, jsonify
import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = '/etc/secrets/breezy-calendar-interation-dab07558a5f0.json'
CALENDAR_ID = 'c_39dbf363c487045db93009e4f1bcaf7209d9c6f18c820a09e4992adbd22b49e9@group.calendar.google.com'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)

def get_events(start_time, end_time):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def find_open_slots(date, slot_duration_minutes=60):
    work_start = datetime.datetime.combine(date, datetime.time(9, 0))
    work_end = datetime.datetime.combine(date, datetime.time(17, 0))
    events = get_events(work_start, work_end)

    busy_times = [
        (
            datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')),
            datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
        ) for event in events
    ]

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

    return available_slots

@app.route("/", methods=["GET"])
def home():
    return "✅ Webhook is alive!"

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("✅ Webhook called at /get_availability")

    data = request.get_json(silent=True)
    tag = data.get("fulfillmentInfo", {}).get("tag")
    parameters = data.get("sessionInfo", {}).get("parameters", {})
    screens_needed = parameters.get("screens_needed")
    appointment_date_str = parameters.get("appointment_date")
    showing_more_slots = parameters.get("showing_more_slots", False)

    if not appointment_date_str:
        appointment_date_str = datetime.date.today().isoformat()

    appointment_date = datetime.datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    slots = find_open_slots(appointment_date)
    booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

    formatted_slots = [
        f"{appointment_date.strftime('%A, %B %d')} at {slot['start'][11:16]}"
        for slot in slots
    ]

    # If user clicked "See more options"
    if tag == "get_more_slots" or showing_more_slots:
        print("🔁 Showing more slot options (without repeating full flow)")
        chips = {
            "richContent": [[
                {
                    "type": "chips",
                    "options": [
                        {"text": slot, "link": booking_link}
                        for slot in formatted_slots[1:4]
                    ] + [
                        {"text": "See Full Booking Calendar", "link": booking_link}
                    ]
                }
            ]]
        }
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["Here are a few more times you can book:"]}},
                    {"payload": chips}
                ]
            }
        }), 200

    # If no slots found
    if not slots:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["❌ No available times found."]}},
                    {"payload": {
                        "richContent": [[
                            {"type": "chips", "options": [
                                {"text": "See Full Booking Calendar", "link": booking_link}
                            ]}
                        ]]
                    }}
                ]
            }
        }), 200

    # Normal response — first slot + follow up
    first_slot = formatted_slots[0]
    chips = {
        "richContent": [[
            {
                "type": "chips",
                "options": [
                    {"text": "Yes, that time works"},
                    {"text": "See more options"}
                ]
            }
        ]]
    }

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have an opening for {first_slot}! Does this time work, or would you like to see more options?"
                ]}},
                {"payload": chips}
            ]
        }
    }), 200


    # ------------------------
    # Default response (first slot only)
    # ------------------------
    if not slots:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["❌ Sorry, no available times on that day."]}},
                    {"text": {"text": ["You can check our full booking calendar:"]}},
                    {"payload": {
                        "richContent": [[
                            {"type": "chips", "options": [
                                {"text": "See Full Booking Calendar", "link": booking_link}
                            ]}
                        ]]
                    }}
                ]
            }
        }), 200

    first_slot = formatted_slots[0]
    chips = {
        "richContent": [[
            {
                "type": "chips",
                "options": [
                    {"text": "Yes, that time works"},
                    {"text": "See more options"}
                ]
            }
        ]]
    }

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have an opening for {first_slot}! Does this time work, or would you like to see more options?"
                ]}},
                {"payload": chips}
            ]
        }
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
