import httpx
from app.core.config import settings

TOKEN_API_URL = settings.TOKEN_API_URL
CHECK_TOKEN_API_URL = settings.CHECK_TOKEN_API_URL


async def report_and_get_remaining_tokens(user_id: str, amount: int) -> int:
    """
    Reports token usage to the backend and returns the remaining token count.
    Returns -1 if reporting fails or user lacks enough tokens.
    """
    if not TOKEN_API_URL or not user_id or amount == 0:
        print("Skipping token report: Missing URL, user_id, or amount is zero.")
        return -1

    payload = {"userId": user_id, "amount": amount}

    try:
        async with httpx.AsyncClient() as client:
            print(f"--> Calling token API for user {user_id} with amount {amount}")
            response = await client.post(TOKEN_API_URL, json=payload, timeout=10.0)

            print(f"Token API Response Status: {response.status_code}")

            try:
                response_json = response.json()
                print(f"Token API Response Body: {response_json}")
            except Exception:
                response_json = {}
                print(f"Token API Response Body (not JSON): {response.text}")

            if response.status_code == 200:
                remaining = response_json.get("remaining_token", -1)
                return remaining

            elif response.status_code == 500 and "don't have enough token" in str(response.text).lower():
                print("<-- Token deduction failed: insufficient tokens.")
                return -1

            else:
                print("<-- Token deduction failed: unexpected error.")
                return -1

    except httpx.RequestError as e:
        print(f"Could not connect to token reporting API: {e}")
        return -1


async def check_user_tokens(user_id: str) -> bool:
    """
    Checks if a user has tokens by calling the backend.
    The backend response format:
        { "data": { "has_token": true | false } }
    Returns True if the user has tokens, False otherwise.
    """
    if not CHECK_TOKEN_API_URL or not user_id:
        print("Skipping token check: Missing URL or user_id.")
        return True  # Allow request if API info missing

    payload = {"userId": user_id}

    try:
        async with httpx.AsyncClient() as client:
            print(f"--> Checking tokens for user {user_id}")
            response = await client.post(CHECK_TOKEN_API_URL, json=payload, timeout=10.0)

            if response.status_code != 200:
                print(f"<-- Token check failed with status {response.status_code}. Allowing request to proceed.")
                return True  # Allow if backend temporarily fails

            response_json = response.json()
            print(f"<-- Token check response: {response_json}")

            data = response_json.get("data", {})
            has_token_flag = data.get("has_token")

            if isinstance(has_token_flag, bool):
                print(f"Has_token flag found: {has_token_flag}")
                return has_token_flag
            else:
                print("<-- Unexpected response format. Defaulting to False.")
                return False

    except httpx.RequestError as e:
        print(f"Could not connect to token check API: {e}. Allowing request to proceed.")
        return True
