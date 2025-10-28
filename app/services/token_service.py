import httpx
from app.core.config import settings

TOKEN_API_URL = settings.TOKEN_API_URL
CHECK_TOKEN_API_URL = settings.CHECK_TOKEN_API_URL


async def check_user_tokens(user_id: str) -> bool:
    """
    Checks if a user has tokens by calling the main backend.

    Supports both:
        - 'data.userToken' (numeric balance)
        - 'data.has_token' (boolean flag)

    Returns:
        True  -> if user has tokens
        False -> if user has no tokens
        True  -> if API unreachable (so requests aren’t blocked)
    """

    if not CHECK_TOKEN_API_URL or not user_id:
        print("Skipping token check: Missing URL or user_id.")
        return True  # Allow request to proceed safely

    payload = {"userId": user_id}

    try:
        async with httpx.AsyncClient() as client:
            print(f"--> Checking tokens for user {user_id}")
            response = await client.post(CHECK_TOKEN_API_URL, json=payload, timeout=10.0)

            if response.status_code != 200:
                print(f"<-- Token check failed with status {response.status_code}. Allowing request to proceed.")
                return True

            response_json = response.json()
            print(f"<-- Token check response: {response_json}")

            data = response_json.get("data", {})

            # Handle both response formats gracefully
            token_balance = data.get("userToken")
            has_token_flag = data.get("has_token")

            if isinstance(token_balance, (int, float)):
                has_tokens = token_balance > 0
                print(f"Token balance found: {token_balance}. User has tokens: {has_tokens}")
                return has_tokens

            elif isinstance(has_token_flag, bool):
                print(f"Has_token flag found: {has_token_flag}")
                return has_token_flag

            else:
                print("<-- Unexpected token response format. Defaulting to False.")
                return False

    except httpx.RequestError as e:
        print(f"Could not connect to token check API: {e}. Allowing request to proceed.")
        return True


async def report_and_get_remaining_tokens(user_id: str, amount: int) -> int:
    """
    Reports token usage to the main backend and returns the remaining token count.

    Returns:
        int  -> remaining token count if successful
        -1   -> if operation fails or API returns an error
    """

    if not TOKEN_API_URL or not user_id or amount <= 0:
        print("Skipping token report: Missing URL, user_id, or invalid amount.")
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
                print(f"Token API Response Body (not JSON): {response.text}")
                return -1

            # Check for success and remaining token info
            if response.status_code == 200 and response_json.get("success", False):
                remaining = response_json.get("remaining_token", -1)
                print(f"<-- Token deduction successful. Remaining tokens: {remaining}")
                return remaining

            # Handle specific backend error cases
            message = response_json.get("message", "").lower()
            if "don't have enough token" in message:
                print("<-- Token deduction failed: insufficient tokens.")
                return -1

            print("<-- Token deduction failed: unexpected response.")
            return -1

    except httpx.RequestError as e:
        print(f"Could not connect to token reporting API: {e}")
        return -1