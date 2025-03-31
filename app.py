from flask import Flask, request, jsonify
import requests
from icalendar import Calendar
from datetime import datetime, timedelta, time
import pytz

app = Flask(__name__)

# Config
JOBBER_ICS_URL = "https://secure.getjobber.com/calendar/35357303484436154516213451527256034241560538086184/jobber.ics?at%5B%5D=2398076&ot%5B%5D=basic&ot%5B%5D=reminders&ot%5B%5D=events&ot%5B%5D=visits&ot%5B%5D=assessments&at%5B%5D=-1"
pacific = pytz.timezone("America/Los_Angeles")

def fetch_busy_times():
    try:
        response = requests.get(JOBBER_ICS_URL)
        cal = Calendar.from_ical(response.content)

        busy = []
        for component in cal.walk():
            if component.name == "VEVENT":
                start = component.get('dtstart').dt
                end = component.get('dtend').dt
                if isinstance(start, datetime) and isinstance(end, datetime):
                    busy.append((start.astimezone(pacific), end.astimezone(pacific)))
        return busy
    except Exception as e:
        print("❌ Error fetching .ics:", e)
        return []

def find_open_slots(date, slot_duration_minutes=60):
    work_start = pacific.localize(datetime.combine(date, time(8, 0)))
    work_end = pacific.localize(datetime.combine(date, time(17, 0)))
    busy_times = fetch_busy_times()

    free_times = []
    current_start = work_start
    for busy_start, busy_end in sorted(busy_times):
        if busy_start.date() != date:
            continue
        if current_start < busy_start:
            free_times.append((current_start, busy_start))
        current_start = max(current_start, busy_end)

    if current_start < work_end:
        free_times.append((current_start, work_end))

    slots = []
    for free_start, free_end in free_times:
        slot_start = free_start
        while slot_start + timedelta(minutes=slot_duration_minutes) <= free_end:
            slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
            slots.append({
                'start': slot_start.isoformat(),
                'end': slot_end.isoformat()
            })
            slot_start = slot_end

    return slots

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("✅ Webhook called at /get_availability")
    data = request.get_json(silent=True)
    parameters = data.get("sessionInfo", {}).get("parameters", {})
    tag = data.get("fulfillmentInfo", {}).get("tag", "")
    showing_more_slots = parameters.get("showing_more_slots", False)

    appointment_date_raw = parameters.get("appointment_date")
    appointment_date = None

    try:
        if isinstance(appointment_date_raw, str):
            appointment_date = datetime.strptime(appointment_date_raw[:10], "%Y-%m-%d").date()
        elif isinstance(appointment_date_raw, dict):
            appointment_date = datetime(
                int(appointment_date_raw.get("year")),
                int(appointment_date_raw.get("month")),
                int(appointment_date_raw.get("day"))
            ).date()
        else:
            appointment_date = datetime.now(pacific).date() + timedelta(days=1)

        if appointment_date <= datetime.now(pacific).date():
            appointment_date += timedelta(days=7)
    except Exception as e:
        print("❌ Error parsing date:", e)
        appointment_date = datetime.now(pacific).date() + timedelta(days=1)

    print(f"📆 Checking availability for: {appointment_date}")
    slots = find_open_slots(appointment_date)

    booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
    formatted_slots = [
        f"{appointment_date.strftime('%A, %B %d')} at {slot['start'][11:16]}"
        for slot in slots
    ]

    if tag == "get_more_slots" or showing_more_slots:
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
                    {"payload": {
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
                    }}
                ]
            }
        })

    if not slots:
        return jsonify({
            "fulfillment_response": {
                "messages": [{"text": {"text": ["❌ No availability found."]}}]
            }
        })

    first_slot = formatted_slots[0]
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

@app.route("/", methods=["GET"])
def home():
    return "✅ Breezy is running with Jobber .ics calendar sync!"
