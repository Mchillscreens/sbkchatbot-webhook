@app.route("/get_availability", methods=["POST"])
def get_availability():
    print("Webhook called!")

    data = request.get_json(silent=True)
    print("Request data:", data)

    screens_needed = data.get("sessionInfo", {}).get("parameters", {}).get("screens_needed")
    print(f"screens_needed: {screens_needed}")

    if not screens_needed:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [
                        "How many screens need service?"
                    ]}}
                ]
            }
        })

    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [
                    f"We have time slots for {screens_needed} screens. Ready to book?"
                ]}}
            ]
        }
    })
