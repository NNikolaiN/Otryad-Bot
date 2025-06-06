import json
import os
import time

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Исправляем структуру users, если она список
            if isinstance(data.get("users"), list):
                print("Warning: 'users' is a list, converting to dict")
                data["users"] = {}
            return data
    # Возвращаем словарь по умолчанию
    return {"buttons": {}, "users": {}, "receipts": [], "receipt_history": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_buttons():
    return load_data().get("buttons", {})

def get_users():
    return load_data().get("users", {})

def add_user(user_id):
    data = load_data()
    if not isinstance(data["users"], dict):
        print("Error: 'users' is not a dict, resetting to dict")
        data["users"] = {}
    data["users"][str(user_id)] = {"joined": time.time()}
    save_data(data)

def add_receipt(user_id, file_id, file_type):
    data = load_data()
    data["receipts"].append({
        "user_id": user_id,
        "file_id": file_id,
        "type": file_type,
        "status": "pending",
        "timestamp": time.time()
    })
    save_data(data)

def add_receipt_history(user_id, timestamp):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data["receipt_history"]:
        data["receipt_history"][user_id_str] = []
    data["receipt_history"][user_id_str].append(timestamp)
    save_data(data)

def get_receipt_history(user_id):
    data = load_data()
    return data["receipt_history"].get(str(user_id), [])

def clean_receipt_history(user_id):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data["receipt_history"]:
        return
    current_time = time.time()
    data["receipt_history"][user_id_str] = [
        ts for ts in data["receipt_history"][user_id_str]
        if current_time - ts < 7200
    ]
    save_data(data)

def update_button(button_name, button_data):
    data = load_data()
    data["buttons"][button_name] = button_data
    save_data(data)

def add_message_to_button(button_name, message_data):
    data = load_data()
    if button_name not in data["buttons"]:
        data["buttons"][button_name] = {"messages": [], "active": True}
    data["buttons"][button_name]["messages"].append(message_data)
    save_data(data)

def toggle_button(button_name, active):
    data = load_data()
    if button_name in data["buttons"]:
        data["buttons"][button_name]["active"] = active
        save_data(data)

def remove_message_from_button(button_name, index):
    data = load_data()
    if button_name in data["buttons"] and 0 <= index < len(data["buttons"][button_name]["messages"]):
        data["buttons"][button_name]["messages"].pop(index)
        save_data(data)

def get_receipts():
    return load_data().get("receipts", [])

def update_receipt_status(user_id, file_id, status):
    data = load_data()
    for receipt in data["receipts"]:
        if receipt["user_id"] == user_id and receipt["file_id"] == file_id:
            receipt["status"] = status
            break
    save_data(data)