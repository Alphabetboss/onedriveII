# answer_engine.py

def get_answer(question):
    # Replace this with your actual ML model or logic
    # For now, a simple hardcoded example:
    if "water" in question.lower():
        return "Watering is recommended when soil moisture is below 30%."
    elif "temperature" in question.lower():
        return "Ideal temperature for irrigation is between 15°C and 25°C."
    else:
        return "Sorry, I don't have an answer for that yet."

