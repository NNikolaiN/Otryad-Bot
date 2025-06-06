from typing import List

def validate_config(token: str, admins: List[int]) -> None:
    if not isinstance(token, str) or not token:
        raise ValueError("TOKEN must be a non-empty string")
    if not isinstance(admins, list) or not all(isinstance(x, int) for x in admins):
        raise ValueError("ADMINS must be a list of integers")

TOKEN = "8090133594:AAElVyM5K9ndNJ9TnnokO7kFZw6gqZgeS4s"
ADMINS = [6255992744, 640705464]

validate_config(TOKEN, ADMINS)
