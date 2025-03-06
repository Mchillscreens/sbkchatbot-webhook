def get_free_slots():
    """Fetches and parses the Jobber iCal feed to find available time slots."""
    try:
        print("Fetching calendar data...")  # ✅ Debugging log

        # ✅ Limit request time to 5 seconds
        response = requests.get(ICAL_URL, timeout=5)  
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

        # ✅ Get current time in UTC (timezone-aware)
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        end_of_week = now + datetime.timedelta(days=7)

        # ✅ Create a set instead of a list for fast lookups
        busy_times = set()
        for event in calendar.events:
            event_start = event.begin.datetime
            event_end = event.end.datetime

            # Ensure event times are also timezone-aware
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=pytz.utc)
            if event_end.tzinfo is None:
                event_end = event_end.replace(tzinfo=pytz.utc)

            if now <= event_start <= end_of_week:
                busy_times.add(event_start.date())  # ✅ Store only start dates for efficiency

        # ✅ Finding free days (only one button per day)
        free_slots = {}
        previous_end = now

        for day in range(8):  # ✅ Check each day in the next week
            check_day = (now + datetime.timedelta(days=day)).date()

            if check_day not in busy_times:  # ✅ Faster lookup with set
                formatted_date = format_date_short(check_day)  # Convert to MM/DD/YY format
                
                # ✅ Only add one button per day
                free_slots[check_day] = {
                    "text": formatted_date,
                    "postback": BOOKING_URL
                }
                
            previous_end += datetime.timedelta(days=1)

        buttons = list(free_slots.values())

        # ✅ Always add a "See All Available" button at the end
        buttons.append({
            "text": "See All Available",
            "postback": BOOKING_URL
        })

        # ✅ Log available slots for debugging
        print("Available Slots:", buttons)

        # ✅ Return JSON in simpler format for Dialogflow CX
        return {
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["Select an available date:"]}},
                    *[
                        {"text": {"text": [f"{slot['text']} → {slot['postback']}"]}}
                        for slot in buttons
                    ]
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

