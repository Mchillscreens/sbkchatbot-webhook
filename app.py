from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Webhook is alive!"

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("✅ Webhook called at /get_availability")

    data = request.get_json(silent=True)

    print("📦 Raw Request (request.data):", request.data)
    print("📦 Parsed JSON (data):", data)

    if data is None:
        print("❗ No JSON data received.")
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "❗ Error: No valid JSON data received."
                    ]}}
                ]
            }
        })

    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    print(f"🖼️ screens_needed: {screens_needed}")

    if not screens_needed:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "How many screens do you need serviced?"
                    ]}}
                ]
            }
        })

    time_slots = [
        "Tuesday, March 19th at 10:00 AM",
        "Wednesday, March 20th at 2:00 PM",
        "Thursday, March 21st at 9:00 AM"
    ]

    chips = {
        "richContent": [
            [
                {
                    "type": "chips",
                    "options": [
                        {
                            "text": slot,
                            "link": "https://clienthub.getjobber.com/booking/53768b13-9e9c-43b6-8f7f-6f53ef831bb4"
                        } for slot in time_slots
                    ]
                }
            ]
        ]
    }

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have openings for {screens_needed} screens! Pick a time below to book:"
                ]}},
                {"payload": chips}
            ]
        }
    })

if __name__ == "__main__":
    print("✅ Starting Flask App")
    port = int(os.environ.get("PORT", 5000))  # 🔥 THIS is the Render fix
    app.run(debug=True, host="0.0.0.0", port=port)
