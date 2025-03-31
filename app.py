from flask import Flask, request, jsonify
import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz
import requests
from dateutil import parser as date_parser

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = '/etc/secrets/breezy-calendar-interation-dab07558a5f0.json'
CALENDAR_ID = 'r8d5g7e7rkj325b5aflt21infkrtmocu@import.calendar.google.com'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)
pacific = pytz.timezone("America/Los_Angeles")

def get_events(start_time, end_time):
    if start_time.tzinfo is None:
        start_time = pacific.localize(start_time)
    else:
        start_time = start_time.astimezone(pacific)

    if end_time.tzinfo is None:
        end_time = pacific.localize(end_time)
    else:
        end_time = end_time.astimezone(pacific)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def find_open_slots(date, slot_duration_minutes=60):
    work_start = pacific.localize(datetime.datetime.combine(date, datetime.time(8, 0)))
    work_end = pacific.localize(datetime.datetime.combine(date, datetime.time(17, 0)))
    events = get_events(work_start, work_end)

    busy_times = [
        (
            date_parser.parse(event['start']['dateTime']),
            date_parser.parse(event['end']['dateTime'])
        ) for event in events if 'dateTime' in event['start'] and 'dateTime' in event['end']
    ]

    print(f"📆 Busy times on {date}:")
    for b_start, b_end in busy_times:
        print(f"⛔ {b_start.time()} to {b_end.time()}")

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

            # DEBUG: Show comparisons between slot and all busy times
            print(f"🔍 Checking slot {slot_start.time()}–{slot_end.time()} vs busy:")
            for b_start, b_end in busy_times:
                print(f"    ⛔ {b_start.time()} to {b_end.time()}")

            if not any(start < slot_end and slot_start < end for start, end in busy_times):
                available_slots.append({
                    'start': slot_start.isoformat(),
                    'end': slot_end.isoformat()
                })

            slot_start = slot_end

    print(f"✅ Found {len(available_slots)} available slots.")
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
    appointment_date_raw = parameters.get("appointment_date")
    showing_more_slots = parameters.get("showing_more_slots", False)

    appointment_date = None
    if isinstance(appointment_date_raw, str):
        print(f"🧪 Raw appointment string: {appointment_date_raw}")
        try:
            appointment_date = datetime.datetime.strptime(appointment_date_raw[:10], '%Y-%m-%d').date()
            if appointment_date <= datetime.date.today():
                appointment_date += datetime.timedelta(days=7)
        except Exception as e:
            print("❌ Error parsing appointment date string:", str(e))
            appointment_date = datetime.date.today() + datetime.timedelta(days=1)

    elif isinstance(appointment_date_raw, dict):
        try:
            appointment_date = datetime.date(
                int(appointment_date_raw.get("year", 2025)),
                int(appointment_date_raw.get("month", 1)),
                int(appointment_date_raw.get("day", 1))
            )
            if appointment_date <= datetime.date.today():
                appointment_date += datetime.timedelta(days=7)
        except Exception as e:
            print("❌ Error parsing appointment date object:", str(e))
            appointment_date = datetime.date.today() + datetime.timedelta(days=1)
    else:
        appointment_date = datetime.date.today() + datetime.timedelta(days=1)

    print(f"🗓️ Parsed appointment date: {appointment_date}")

    slots = find_open_slots(appointment_date)
    booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

    formatted_slots = [
        f"{appointment_date.strftime('%A, %B %d')} at {slot['start'][11:16]}"
        for slot in slots
    ]

    if tag == "get_more_slots" or showing_more_slots:
        print("🔁 Showing more slot options")
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
            "sessionInfo": {
                "parameters": {
                    "showing_more_slots": False,
                    "booking_flow_completed": True
                }
            },
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["Here are a few more times you can book:"]}},
                    {"payload": chips}
                ]
            }
        }), 200

    if not slots:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["❌ No available times found."]}},
                    {"payload": {
                        "richContent": [[
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "See Full Booking Calendar", "link": booking_link}
                                ]
                            }
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
        "sessionInfo": {
            "parameters": {
                "showing_more_slots": False,
                "booking_flow_completed": True
            }
        },
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have an opening for {first_slot}! Does this time work, or would you like to see more options?"
                ]}},
                {"payload": chips}
            ]
        }
    }), 200

@app.route("/send_to_zapier", methods=["POST"])
def send_to_zapier():
    data = request.get_json(silent=True)
    print("📨 /send_to_zapier was called")
    print("Incoming data:", data)

    params = data.get("sessionInfo", {}).get("parameters", {})

    payload = {
        "name": params.get("user_name"),
        "email": params.get("user_email"),
        "phone": params.get("user_phone"),
        "appointment_date": params.get("appointment_date"),
        "screens_needed": params.get("screens_needed")
    }

    zapier_url = "https://hooks.zapier.com/hooks/catch/22255277/2c28k46/"
    try:
        zapier_response = requests.post(zapier_url, json=payload, timeout=5)
        print("📤 Sent to Zapier. Status:", zapier_response.status_code)
        print("🔁 Zapier Response:", zapier_response.text)
    except Exception as e:
        print("❌ Error sending to Zapier:", str(e))

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {
                    "text": {
                        "text": [
                            "✅ I’ve sent your booking details — you’re all set! We'll follow up soon to confirm your appointment."
                        ]
                    }
                }
            ]
        },
        "sessionInfo": {
            "parameters": {
                "booking_flow_completed": True,
                "showing_more_slots": False
            }
        }
    }), 200
