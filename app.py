from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Webhook is alive!"

@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("✅ Webhook called at /get_availability")

    # Grab JSON from Dialogflow CX or Postman
    data = request.get_json(silent=True)
    
    # Debug prints to help troubleshoot
    print("📦 Raw Request (request.data):", request.data)        # This prints the raw incoming data
    print("📦 Parsed JSON (data):", data)                        # This prints what Flask parsed

    # Extract screens_needed from parameters (only if data is not None)
    if data is None:
        print("❗ No JSON data received. Check Content-Type header and request body format.")
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "❗ Error: No valid JSON data received. Please check the request format!"
                    ]}}
                ]
            }
        })

    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    print(f"🖼️ screens_needed: {screens_needed}")

    if not screens_needed:
        print("❗ No screen count provided. Prompting user again...")
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "I need to know how many screens need service to show you the best available time slots!"
                    ]}}
                ]
            }
        })

    # Return available slots message
    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"✅ We have time slots for {screens_needed} screens. Ready to book?"
                ]}}
            ]
        }
    })

if __name__ == "__main__":
    print("✅ Starting Flask App (with get_availability and debug)")
    app.run(debug=True, host="0.0.0.0", port=5000)
