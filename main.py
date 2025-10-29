from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from parser import parse_upi_message
from datetime import datetime
from bson import ObjectId

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# MongoDB setup
client = MongoClient("mongodb url")
db = client["expense_tracker"]
expenses = db["expenses"]
budgets = db["budgets"]

# Welcome page
@app.get("/")
def welcome(request: Request):
    return templates.TemplateResponse("welcome.html", {"request": request})

# Add message page
@app.get("/add-message")
def add_message_page(request: Request):
    return templates.TemplateResponse("add_message.html", {"request": request})

# Handle UPI message submission
@app.post("/add-message")
def add_message(request: Request, message: str = Form(...)):
    try:
        parsed = parse_upi_message(message)
        print(f"Parsed message: {parsed} (type: {type(parsed)})")
        if parsed and isinstance(parsed, dict):
            amount = parsed.get("amount")
            try:
                amount = float(amount)
                parsed["amount"] = amount
            except (TypeError, ValueError):
                print(f"❌ Parsed message has invalid amount: {parsed}")
                return templates.TemplateResponse("add_message.html", {
                    "request": request,
                    "message": "❌ Invalid amount in message. Please check your input."
                })
            # Always set date to now so expense appears in the correct month and day
            parsed["date"] = datetime.now()
            # Ensure amount is float and category is string
            parsed["amount"] = float(parsed["amount"])
            parsed["category"] = str(parsed.get("category", "Other"))
            try:
                result = expenses.insert_one(parsed)
                print(f"[DEBUG] Inserted expense with _id: {result.inserted_id}")
            except Exception as db_exc:
                print(f"❌ Failed to insert expense into MongoDB: {db_exc}")
                return templates.TemplateResponse("add_message.html", {
                    "request": request,
                    "message": "❌ Failed to save expense to database. Please try again."
                })
        else:
            print("❌ Failed to parse message:", message)
            return templates.TemplateResponse("add_message.html", {
                "request": request,
                "message": "❌ Failed to parse message. Please check your input."
            })
    except Exception as e:
        import traceback
        print("❌ Error while adding message:", e)
        traceback.print_exc()
        return templates.TemplateResponse("add_message.html", {
            "request": request,
            "message": f"❌ Error: {e}"
        })
    return RedirectResponse("/summary?msg=Expense+added+successfully!", status_code=302)

# Show summary of expenses
@app.get("/summary")
def show_summary(request: Request):
    try:
        all_expenses = list(expenses.find())
        valid_expenses = []
        total = 0.0
        categories = {}
        for exp in all_expenses:
            amount = exp.get("amount")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                print(f"Skipping expense with invalid amount: {exp}")
                continue
            exp["amount"] = amount
            # Ensure date is a Python datetime object
            date_val = exp.get("date")
            if date_val is not None:
                if not isinstance(date_val, datetime):
                    try:
                        # Try to parse ISO format string
                        exp["date"] = datetime.fromisoformat(str(date_val))
                    except Exception:
                        exp["date"] = datetime.now()
            else:
                exp["date"] = datetime.now()
            valid_expenses.append(exp)
            category = exp.get("category", "Other")
            categories[category] = categories.get(category, 0) + amount
            total += amount
        # Get all months with budgets
        all_budgets = list(budgets.find())
        months = sorted([b["month"] for b in all_budgets])
        # Get selected month from query param, else use current month
        selected_month = request.query_params.get("month")
        if not selected_month:
            selected_month = datetime.now().strftime('%B').lower()  # e.g., 'july'
        # Find budget for selected month, else use latest budget
        budget_doc = None
        for b in all_budgets:
            if b["month"].lower() == selected_month:
                budget_doc = b
                break
        if not budget_doc and all_budgets:
            budget_doc = max(all_budgets, key=lambda b: b["month"])
            selected_month = budget_doc["month"].lower()
        budget = budget_doc["amount"] if budget_doc else 0.0
        # Filter expenses and categories for selected month (by month name, case-insensitive)
        print(f"[DEBUG] Selected month: {selected_month}")
        for e in valid_expenses:
            print(f"[DEBUG] Expense date: {e['date']} (type: {type(e['date'])})")
        filtered_expenses = [e for e in valid_expenses if e["date"].strftime('%B').lower() == selected_month]
        filtered_total = sum(e["amount"] for e in filtered_expenses)
        filtered_categories = {}
        for exp in filtered_expenses:
            category = exp.get("category", "Other")
            filtered_categories[category] = filtered_categories.get(category, 0) + exp["amount"]
        # If there are no categories (no expenses), add a 'No Data' placeholder for the pie chart
        if not filtered_categories:
            filtered_categories = {"No Data": 1}
        balance = budget - filtered_total
        over_budget = filtered_total > budget if budget else False
        # Get message from query params if present
        msg = request.query_params.get("msg", "")
        return templates.TemplateResponse("summary.html", {
            "request": request,
            "expenses": filtered_expenses,
            "total": filtered_total,
            "categories": filtered_categories,
            "message": msg,
            "budget": budget,
            "balance": balance,
            "over_budget": over_budget,
            "months": months,
            "selected_month": selected_month
        })
    except Exception as e:
        import traceback
        print("❌ Error loading summary:", e)
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": str(e)
        })

# Budget input page
@app.get("/add-budget")
def add_budget_page(request: Request):
    return templates.TemplateResponse("add_budget.html", {"request": request, "message": ""})

# Handle budget form submission
@app.post("/add-budget")
def add_budget(request: Request, amount: float = Form(...), month: str = Form(...)):
    try:
        budgets.replace_one({"month": month}, {"month": month, "amount": amount}, upsert=True)
        return templates.TemplateResponse("add_budget.html", {
            "request": request,
            "message": "✅ Budget added successfully!"
        })
    except Exception as e:
        print("❌ Error adding budget:", e)
        return templates.TemplateResponse("add_budget.html", {
            "request": request,
            "message": "❌ Failed to add budget. Please try again."
        })
