# ... everything above remains unchanged

    if not slots:
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": ["❌ No available times found."]}},
                    {"payload": {
                        "richContent": [[
                            {
                                "type": "chips",
                                "options": [
                                    {"text": "See Full Booking Calendar", "link": booking_link}
                                ]
                            }
                        ]]
                    }}
                ]
            }
        }), 200

# ... rest of file unchanged
