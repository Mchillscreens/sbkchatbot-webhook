import os
from flask import Flask, request, jsonify
import requests
import datetime
from ics import Calendar
import pytz

app = Flask(__name__)  # ✅ Define the Flask app

# ✅ Get port from environment variable (Render requires this)
PORT = int(os.environ.get("PORT", 5000))

# Your Jobber booking link
BOOKING_URL = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

# Your Jobber iCal URL
ICAL_URL = "https://secure.getjobber.com/calendar/35357303484436154516213451527256034241560538086184/jobber.ics"


def format_date_short(dt):
    """Formats datetime into 'MM/DD/YY' format for button text."""
    try:
        return dt.strftime("%-m/%-d/%y")  # Unix/Linux/Mac
    except:
        return dt.strftime("%#m/%#d/%y")  # Windows fallback


def get_free_slots():
    """Fetches and parses the Jobber iCal feed to find available time slots."""
    try:
        print("Fetching calendar data...")

        response = requests.get(ICAL_URL, timeout=5)
        if response.status_code != 200:
            print("Error: Failed to fetch calendar data")
            return {
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": ["Error: Could not retrieve calendar data."]}}
                    ]
                }
            }

        calendar = Calendar(response.text)

        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        end_of_week = now + datetime.timedelta(days=7)

        busy_times = set()
        for event in calendar.events:
            event_start = event.begin.datetime
            event_end = event.end.datetime

            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=pytz.utc)
            if event_end.tzinfo is None:
                event_end = event_end.replace(tzinfo=pytz.utc)

            if now <= event_start <= end_of_week:
                busy_times.add(event_start.date())

        free_slots = {}

        # ✅ Loop through the next 8 days, starting tomorrow
        for day in range(8):  
            check_day = (now + datetime.timedelta(days=day)).date()

            # ✅ Skip today (same-day booking not allowed)
            if check_day == now.date():
                continue

            if check_day not in busy_times:
                formatted_date = format_date_short(check_day)

                free_slots[check_day] = {
                    "text": formatted_date,
                    "postback": BOOKING_URL
                }

        buttons = list(free_slots.values())

        # ✅ Add "See All Available" button
        buttons.append({
            "text": "See All Available",
            "postback": BOOKING_URL
        })

        print("Available Slots:", buttons)

        # ✅ Build Rich Content JSON for Dialogflow CX
        rich_buttons = []
        for slot in buttons:
            rich_buttons.append({
                "type": "button",
                "icon": {
                    "type": "chevron_right",
                    "color": "#FF9800"
                },
                "text": slot['text'],
                "link": slot['postback']
            })

        return {
            "fulfillment_response": {
                "messages": [
                    {
                        "payload": {
                            "richContent": [
                                [
                                    {
                                        "type": "list",
                                        "title": "Select an available date:",
                                        "subtitle": "Click a date below to book your appointment."
                                    },
                                    *rich_buttons
                                ]
                            ]
                        }
                    }
                ]
            }
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [f"Error fetching availability: {str(e)}"]}}
                ]
            }
        }


@app.route("/get_availability", methods=["POST"])
def get_availability():
    """Handles webhook requests and returns available slots."""
    print("Webhook called!")
    free_slots = get_free_slots()
    return jsonify(free_slots)


# ✅ Ensure it binds to the correct host and port for Render deployment
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
