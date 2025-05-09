from flask import Flask, request, jsonify
import datetime
import requests
import pytz
from dateutil import parser as date_parser
from ics import Calendar
import re
import pendulum

app = Flask(__name__)
pacific = pytz.timezone("America/Los_Angeles")
JOBBER_ICS_URL = "https://secure.getjobber.com/calendar/35357303484436154516213451527256034241560538086184/jobber.ics?at%5B%5D=2398076&ot%5B%5D=basic&ot%5B%5D=reminders&ot%5B%5D=events&ot%5B%5D=visits&ot%5B%5D=assessments&at%5B%5D=-1"
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/22255277/2c28k46/"

def get_busy_times(date):
    response = requests.get(JOBBER_ICS_URL)
    calendar = Calendar(response.text)
    busy = []

    # ❌ OLD: This passes a DateTime into .on(), which causes the error.
    # p_date = pendulum.parse(str(date))
    # for event in calendar.timeline.on(p_date):

    # ✅ NEW: Use `timeline.start_after()` instead, with a full-day range.
    day_start = pendulum.datetime(date.year, date.month, date.day, 0, 0, 0, tz=pacific)
    day_end = day_start.add(days=1)
    for event in calendar.timeline.start_after(day_start):
        if event.begin >= day_end:
            break
        start = event.begin.astimezone(pacific).replace(tzinfo=None)
        end = event.end.astimezone(pacific).replace(tzinfo=None)
        busy.append((start, end))

    return sorted(busy)


def find_open_slots(date, slot_duration_minutes=60):
    work_start = datetime.datetime.combine(date, datetime.time(8, 0))
    work_end = datetime.datetime.combine(date, datetime.time(17, 0))
    busy_times = get_busy_times(date)

    free_times = []
    current = work_start
    for busy_start, busy_end in busy_times:
        if current < busy_start:
            free_times.append((current, busy_start))
        current = max(current, busy_end)
    if current < work_end:
        free_times.append((current, work_end))

    available_slots = []
    for start, end in free_times:
        slot_start = start
        while slot_start + datetime.timedelta(minutes=slot_duration_minutes) <= end:
            slot_end = slot_start + datetime.timedelta(minutes=slot_duration_minutes)
            available_slots.append({
                'start': slot_start,
                'end': slot_end
            })
            slot_start = slot_end

    return available_slots

@app.route("/", methods=["GET"])
def home():
    return "✅ Breezy webhook is live — using Jobber .ics calendar!"

@app.route("/get_availability", methods=["POST"])
def get_availability():
    data = request.get_json(silent=True)
    tag = data.get("fulfillmentInfo", {}).get("tag", "")
    parameters = data.get("sessionInfo", {}).get("parameters", {})
    screens_raw = parameters.get("screens_needed", 1)

    try:
        screens = int(re.search(r"\d+", str(screens_raw)).group())
    except:
        screens = 1

    duration = max(60, screens * 20)
    today = datetime.datetime.now(pacific).date()

    if tag == "availability_next":
        for i in range(1, 11):
            check_date = today + datetime.timedelta(days=i)
            if check_date.weekday() >= 5:
                continue
            slots = find_open_slots(check_date, duration)
            if slots:
                slot = slots[0]
                formatted = "{} at {}".format(
                    check_date.strftime('%A, %B %d'),
                    slot['start'].strftime("%I:%M %p").lstrip("0")
                )
                return jsonify({
                    "sessionInfo": {
                        "parameters": {
                            "booking_flow_completed": False
                        }
                    },
                    "fulfillment_response": {
                        "messages": [
                            {"text": {"text": [
                                "✅ Our next available time is {}. Does that work for you?".format(formatted)
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

        return jsonify({
            "fulfillment_response": {
                "messages": [{"text": {"text": [
                    "❌ No available times found in the next 10 days."
                ]}}]
            }
        })

    if tag == "get_more_slots":
        all_slots = []
        for i in range(1, 15):
            check_date = today + datetime.timedelta(days=i)
            if check_date.weekday() >= 5:
                continue
            slots = find_open_slots(check_date, duration)
            for slot in slots:
                label = "{} at {}".format(
                    check_date.strftime('%A, %B %d'),
                    slot['start'].strftime("%I:%M %p").lstrip("0")
                )
                all_slots.append(label)
                if len(all_slots) == 10:
                    break
            if len(all_slots) == 10:
                break

        booking_link = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
        return jsonify({
            "sessionInfo": {
                "parameters": {
                    "showing_more_slots": False,
                    "booking_flow_completed": True
                }
            },
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["📋 Here are the next 10 available appointment slots:"]}},
                    {"payload": {
                        "richContent": [[
                            {
                                "type": "chips",
                                "options": [{"text": s} for s in all_slots] + [
                                    {"text": "See Full Booking Calendar", "link": booking_link}
                                ]
                            }
                        ]]
                    }}
                ]
            }
        })

    return jsonify({
        "fulfillment_response": {
            "messages": [{"text": {"text": ["⚠️ No matching tag."]}}]
        }
    })

@app.route("/send_booking_request", methods=["POST"])
def send_booking_request():
    data = request.get_json(silent=True)
    parameters = data.get("sessionInfo", {}).get("parameters", {})

    first_name = parameters.get("first-name", "")
    last_name = parameters.get("last-name", "")
    email = parameters.get("email", "")
    phone = parameters.get("phone", "")
    screens_needed = parameters.get("screens_needed", "")
    service_address = parameters.get("service_address", "")  # ✅ NEW

    payload = {
    "first_name": first_name,
    "last_name": last_name,
    "email": email,
    "phone": phone,
    "street_address": parameters.get("street_address", "Not provided"),
    "city": parameters.get("city", "Not provided"),
    "state": parameters.get("state", "Not provided"),
    "zip_code": parameters.get("zip_code", "Not provided"),
    "screens_needed": screens_needed,
    "frame_color": parameters.get("frame_color", "Not provided"),
    "screen_material": parameters.get("screen_material", "Not provided"),
    "special_conditions": parameters.get("special_conditions", "Not provided"),
}

    response = requests.post(ZAPIER_WEBHOOK_URL, json=payload)
    print("📤 Sent to Zapier:", payload)
    print("📬 Zapier response:", response.status_code)

    return jsonify({
        "fulfillment_response": {
            "messages": [{"text": {"text": [
                "📬 Your booking request was submitted! We’ll follow up shortly to confirm your appointment."
            ]}}]
        }
    })
