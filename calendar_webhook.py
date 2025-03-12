import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Get port from environment variable (Render requires this)
PORT = int(os.environ.get("PORT", 5000))

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("Webhook called!")

    # Get JSON data from Dialogflow
    data = request.get_json(silent=True)
    print("Request data:", data)

    # Extract screens_needed from the request payload
    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    print(f"screens_needed: {screens_needed}")

    # If no screen count, prompt again
    if not screens_needed:
        print("No screen count provided. Prompting user again...")
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "I need to know how many screens need service to show you the best available time slots!"
                    ]}}
                ]
            }
        })

    # Simulate available time slots
    available_slots = [
        {
            "type": "button",
            "icon": {
                "type": "chevron_right",
                "color": "#FF9800"
            },
            "text": "Thursday 10AM",
            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
        },
        {
            "type": "button",
            "icon": {
                "type": "chevron_right",
                "color": "#FF9800"
            },
            "text": "Friday 2PM",
            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
        },
        {
            "type": "button",
            "icon": {
                "type": "chevron_right",
                "color": "#FF9800"
            },
            "text": "See All Available",
            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
        }
    ]

    # Return mocked response to Dialogflow CX
    response_payload = {
        "fulfillment_response": {
            "messages": [
                {
                    "payload": {
                        "richContent": [
                            [
                                {
                                    "type": "list",
                                    "title": f"Here are the best time slots for {screens_needed} screens:",
                                    "subtitle": f"Each job requires about {int(screens_needed) * 20} minutes."
                                },
                                *available_slots
                            ]
                        ]
                    }
                }
            ]
        }
    }

    print("Returning response:", response_payload)
    return jsonify(response_payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
