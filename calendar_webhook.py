import os
from flask import Flask, request, jsonify

# Initialize Flask app BEFORE you use it
app = Flask(__name__)

# Get port from environment variable (Render requires this)
PORT = int(os.environ.get("PORT", 5000))

# Root endpoint to confirm the webhook is running
@app.route("/", methods=["GET"])
def home():
    return "Webhook is alive!"

# Webhook endpoint for Dialogflow CX
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

    # Return a simple confirmation message
    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
 

