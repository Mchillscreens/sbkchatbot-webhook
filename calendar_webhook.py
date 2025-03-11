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
