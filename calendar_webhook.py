from flask import Flask, request, jsonify
import requests
import datetime
from ics import Calendar
import pytz

app = Flask(__name__)  # ✅ Define the Flask app

# Your Jobber booking link
BOOKING_URL = "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"

# Your Jobber iCal URL
ICAL_URL = "https://secure.getjobber.com/calendar/35357303484436154516213451527256034241560538086184/jobber.ics"

def format_date_short(dt):
    """Formats datetime into 'MM/DD/YY' format for button text."""
    return dt.strftime("%-m/%-d/%y")  # Example: '3/16/25'

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
                formatted_date = format_date_short(previous_end)  # Convert to MM/DD/YY format
                booking_link = f"{BOOKING_URL}"  # Use the correct Jobber booking link
                
                # Store the date and link in JSON format for proper button formatting
                free_slots.append({
                    "text": formatted_date,
                    "postback": booking_link
                })
                
            previous_end = max(previous_end, end)

        if not free_slots:
            free_slots.append({
                "text": "No available slots",
                "postback": BOOKING_URL
            })

        # ✅ Log available slots for debugging
        print("Available Slots:", free_slots)

        # ✅ Return JSON with proper button formatting
        return {
            "fulfillment_response": {
                "messages": [
                    {
                        "payload": {
                            "richContent": [
                                [
                                    {"type": "text", "text": "Select an available date:"},
                                    *[
                                        {"type": "button", "text": slot["text"], "link": slot["postback"]}
                                        for slot in free_slots
                                    ]
                                ]
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

