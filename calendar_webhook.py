import os
from flask import Flask, request, jsonify
import requests
import datetime
from ics import Calendar
import pytz

app = Flask(__name__)

# Get port from environment variable (Render requires this)
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

def get_free_slots(screens_needed):
    """Fetch and parse the Jobber iCal feed to find available time slots based on screens needed."""
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

        # How much time we need in minutes (each screen needs 20 minutes)
        time_needed_minutes = int(screens_needed) * 20
        time_needed = datetime.timedelta(minutes=time_needed_minutes)

        print(f"Time needed for {screens_needed} screens: {time_needed_minutes} minutes")

        # Collect all events within the time window
        events = []
        for event in calendar.events:
            start = event.begin.datetime.replace(tzinfo=pytz.utc)
            end = event.end.datetime.replace(tzinfo=pytz.utc)
            if now <= start <= end_of_week:
                events.append((start, end))

        # Sort events by start time
        events.sort()

        # Generate possible time slots
        available_slots = []
        search_start = now + datetime.timedelta(days=1)  # Start searching from tomorrow
        search_end = end_of_week

        # Add a dummy event to represent the end of the search period
        events.append((search_end, search_end))

        # Look for gaps between events
        current_time = search_start
        for event_start, event_end in events:
            # Is there enough time between current_time and event_start?
            if current_time + time_needed <= event_start:
                # Slot found!
                slot_date = format_date_short(current_time)
                slot_time = current_time.strftime("%I:%M %p")
                label = f"{slot_date} - {slot_time}"
                available_slots.append({
                    "text": label,
                    "postback": BOOKING_URL
                })

                # Move current_time forward by the job time (optional: or keep the same for multiple slots)
                current_time += time_needed

            # Move current time forward if needed
            if current_time < event_end:
                current_time = event_end

        # If no slots found
        if not available_slots:
            available_slots.append({
                "text": "No suitable time slots found in the next 7 days.",
                "postback": BOOKING_URL
            })

        # Add "See All Available" button at the end
        available_slots.append({
            "text": "See All Available",
            "postback": BOOKING_URL
        })

        print("Available Slots:", available_slots)

        # Build Rich Content JSON for Dialogflow CX
        rich_buttons = []
        for slot in available_slots:
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
                                        "title": f"Here are the best time slots for {screens_needed} screens:",
                                        "subtitle": f"Each job requires about {time_needed_minutes} minutes."
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
        print(f"Error in get_free_slots: {str(e)}")
        return {
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [f"Error fetching availability: {str(e)}"]}}
                ]
            }
        }

@app.route("/get_availability", methods=["POST"])
def get_availability():
    """
    Handles webhook requests and returns available slots.
    """
    print("Webhook called!")

    # Get JSON data from Dialogflow
    data = request.get_json(silent=True)
    print("Request data:", data)

    # Extract screens_needed from the request payload
    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")

    # Require screens_needed before proceeding
    if not screens_needed:
        print("No screen count provided. Prompting user...")
        return {
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "I need to know how many screens need service to show you the best available time slots!"
                    ]}}
                ]
            }
        }

    free_slots = get_free_slots(screens_needed)
    return jsonify(free_slots)

# Ensure it binds to the correct host and port for Render deployment
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

