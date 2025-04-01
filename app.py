from flask import Flask, request, jsonify
import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz
import requests
from dateutil import parser as date_parser
from datetime import timedelta, datetime

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = '/etc/secrets/breezy-calendar-interation-dab07558a5f0.json'
CALENDAR_ID = 'c_39dbf363c487045db93009e4f1bcaf7209d9c6f18c820a09e4992adbd22b49e9@group.calendar.google.com'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)
pacific = pytz.timezone("America/Los_Angeles")

def get_events(start_time, end_time):
    start_time = pacific.localize(start_time)
    end_time = pacific.localize(end_time)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def find_open_slots(date, slot_duration_minutes=60):
    work_start = datetime.combine(date, datetime.time(8, 0))
    work_end = datetime.combine(date, datetime.time(17, 0))
    events = get_events(work_start, work_end)

    busy_times = [
        (
            datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')),
            datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
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
        while slot_start + timedelta(minutes=slot_duration_minutes) <= free_end:
            slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
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
    data = request.get_json(silent=True)
    tag = data.get("fulfillmentInfo", {}).get("tag", "")
    parameters = data.get("sessionInfo", {}).get("parameters", {})

    if tag == "availability_next":
        print("🧠 Handling 'Next Available' request")
        screens_raw = parameters.get("screens_needed", 1)
        try:
            import re
            screens = int(re.search(r"\d+", str(screens_raw)).group())
        except:
            screens = 1
        duration = max(60, screens * 20)

        today = datetime.now(pacific).date()
        found_slot = None
        for i in range(1, 11):  # next 10 days
            check_date = today + timedelta(days=i)
            if check_date.weekday() >= 5:
                continue  # skip weekends
            slots = find_open_slots(check_date, duration)
            if slots:
                found_slot = {
                    "date": check_date,
                    "slot": slots[0]
                }
                break

        if found_slot:
            formatted = f"{found_slot['date'].strftime('%A, %B %d')} at " + date_parser.parse(found_slot['slot']['start']).astimezone(pacific).strftime("%I:%M %p").lstrip("0")
            return jsonify({
                "sessionInfo": {
                    "parameters": {
                        "booking_flow_completed": False
                    }
                },
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [
                            f"✅ Our next available time is {formatted}. Does that work for you?"
                        ]}},
                        {"payload": {
                            "richContent": [[
                                {
                                    "type": "chips",
                                    "options": [
                                        {"text": "Yes, that time works"},
                                        {"text": "See more options"}
                                    ]
                                }
                            ]]
                        }}
                    ]
                }
            })

        else:
            return jsonify({
                "fulfillment_response": {
                    "messages": [{"text": {"text": [
                        "❌ Sorry, we couldn’t find anything in the next 10 days that fits your service time."
                    ]}}]
                }
            })

    print("✅ Webhook called at /get_availability")

    screens_needed = parameters.get("screens_needed")
    appointment_date_raw = parameters.get("appointment_date")
    showing_more_slots = parameters.get("showing_more_slots", False)

    if isinstance(appointment_date_raw, str):
        appointment_date = datetime.strptime(appointment_date_raw, '%Y-%m-%d').date()
        if appointment_date <= datetime.today().date():
            appointment_date += timedelta(days=7)
    elif isinstance(appointment_date_raw, dict):
        appointment_date = datetime(
            int(appointment_date_raw.get("year", 2025)),
            int(appointment_date_raw.get("month", 1)),
            int(appointment_date_raw.get("day", 1))
        ).date()
        if appointment_date <= datetime.today().date():
            appointment_date += timedelta(days=7)
    else:
        appointment_date = datetime.today().date() + timedelta(days=1)

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
    print("📨 /send_to_zapier was called")
    data = request.get_json(silent=True)
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
