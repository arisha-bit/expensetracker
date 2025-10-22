from datetime import datetime
import re

def parse_upi_message(message: str):
    try:
        # Extract amount (support Rs, INR, ₹, etc.)
        # Support numbers with commas (e.g., 1,250.00)
        amount_match = re.search(r'(?:Rs\.?|INR|\u20B9|₹)[ ]*([0-9,]+(?:\.[0-9]+)?)', message, re.IGNORECASE)
        if not amount_match:
            return None
        amount_str = amount_match.group(1).replace(',', '')
        amount = float(amount_str)


        # Extract date in format like 29-Jul-25 if present
        date_match = re.search(r'(\d{1,2})-([A-Za-z]{3})-(\d{2,4})', message)
        if date_match:
            day, mon, year = date_match.groups()
            # Handle 2-digit year (assume 2000+)
            if len(year) == 2:
                year = '20' + year
            try:
                date = datetime.strptime(f"{day}-{mon}-{year}", "%d-%b-%Y")
            except Exception:
                date = datetime.now()
        else:
            date = datetime.now()

        # Simple category detection
        msg_lower = message.lower()
        if "zomato" in msg_lower or "swiggy" in msg_lower:
            category = "Food"
        elif "amazon" in msg_lower or "flipkart" in msg_lower:
            category = "Shopping"
        elif "paytm" in msg_lower or "upi" in msg_lower:
            category = "Transfer"
        else:
            category = "Other"

        return {
            "amount": amount,
            "date": date,
            "category": category
        }
    except Exception as e:
        print("❌ Error parsing message:", e)
        return None
