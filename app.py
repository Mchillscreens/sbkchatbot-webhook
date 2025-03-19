from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Webhook is alive!"

@app.route("/weather", methods=["POST"])
def weather():
    print("✅ Weather webhook called!")
    
    # Return a hardcoded response (no input required)
    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    "Today's weather is sunny with a high of 75°F and a light breeze!"
                ]}}
            ]
        }
    })

if __name__ == "__main__":
    print("✅ Starting Flask App (Weather Webhook)")
    port = int(os.environ.get("PORT", 5000))  # Render dynamic port handling
    app.run(debug=True, host="0.0.0.0", port=port)
