from flask import Flask, request, jsonify
import requests
import datetime
from ics import Calendar
import pytz

app = Flask(__name__)  # ✅ Define the Flask app

# Your Jobber iCal URL
ICAL_URL = "https://secure.getjobber.com/calendar/35357303484436154516213451527256034241560538086184/jobber.ics"

def get_free_slots():
    """Fetches and parses the Jobber iCal feed to find available time slots."""
    try:
        print("Fetching calendar data...")  # ✅ Debugging log

        response = requests.get(ICAL_URL, timeout=10)  # ✅ Added timeout for reliability
        if response.status_code != 200:
            print("Error: Failed to fetch calendar data")  # ✅ Debug log
            return {
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": ["Error: Could not retrieve calendar data."]}}
                    ]
                }
            }

        calendar = Calendar(response.text)

        # Get current time in UTC (timezone-aware)
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        end_of_week = now + datetime.timedelta(days=7)

        busy_times = []
        for event in calendar.events:
            event_start = event.begin.datetime
            event_end = event.end.datetime

            # Ensure event times are also timezone-aware
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=pytz.utc)
            if event_end.tzinfo is None:
                event_end = event_end.replace(tzinfo=pytz.utc)

            if now <= event_start <= end_of_week:
                busy_times.append((event_start, event_end))

        # Finding free time slots
        free_slots = []
        previous_end = now

        for start, end in sorted(busy_times):
            if previous_end < start:
                free_slots.append(
                    f"Available from {previous_end.strftime('%Y-%m-%d %H:%M')} to {start.strftime('%Y-%m-%d %H:%M')}"
                )
            previous_end = max(previous_end, end)

        if not free_slots:
            free_slots.append("No available slots in the next 7 days.")

        # ✅ Log available slots for debugging
        print("Available Slots:", free_slots)

        # ✅ Correctly format the response for Dialogflow CX
        return {
            "fulfillment_response": {
                "messages": [
                    {
                        "text": {
                            "text": [
                                "Here are the available time slots:\n" + "\n".join(free_slots)
                            ]
                        }
                    }
                ]
            }
        }

    except Exception as e:
        print(f"Error: {str(e)}")  # ✅ Log the error
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
    print("Webhook called!")  # ✅ Debugging log
    free_slots = get_free_slots()
    return jsonify(free_slots)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
  # ✅ This starts Flask when running the script

