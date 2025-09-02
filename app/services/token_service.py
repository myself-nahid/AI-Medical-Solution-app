import httpx
from app.core.config import settings

TOKEN_API_URL = settings.TOKEN_API_URL 
CHECK_TOKEN_API_URL = settings.CHECK_TOKEN_API_URL
async def report_and_get_remaining_tokens(user_id: str, amount: int) -> int:
    """
    Reports token usage to the main backend, PRINTS the full response,
    and returns the remaining token count. Returns -1 if the operation fails.
    """
    if not TOKEN_API_URL or not user_id or amount == 0:
        print("Skipping token report: Missing URL, user_id, or amount is zero.")
        return -1 # Return -1 to indicate an error/skip

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
                # Extract the 'remaining_token' from the JSON response
                remaining = response_json.get('remaining_token', -1)
                #print(f"Successfully reported tokens. Remaining for user {user_id}: {remaining}")
                return remaining
            else:
                print(f"Failed to report token usage.")
                return -1

    except httpx.RequestError as e:
        print(f"Could not connect to token reporting API: {e}")
        return -1
    
async def check_user_tokens(user_id: str) -> bool:
    """
    Checks if a user has tokens by calling the main backend.
    Parses the nested response for 'data' -> 'userToken'.
    Returns True if user has tokens (> 0), False otherwise.
    """
    if not CHECK_TOKEN_API_URL or not user_id:
        print("Skipping token check: Missing URL or user_id.")
        return True

    payload = {"userId": user_id}

    try:
        async with httpx.AsyncClient() as client:
            print(f"--> Checking tokens for user {user_id}")
            response = await client.post(CHECK_TOKEN_API_URL, json=payload, timeout=10.0)
            
            if response.status_code == 200:
                response_json = response.json()
                print(f"<-- Token check response: {response_json}")
                
                try:
                    token_balance = response_json.get('data', {}).get('userToken', 0)
                    
                    has_tokens = token_balance > 0
                    
                    print(f"Token balance found: {token_balance}. User has tokens: {has_tokens}")
                    return has_tokens
                    
                except (TypeError, AttributeError):
                    print("<-- Token check response format was unexpected. Defaulting to False.")
                    return False

            else:
                print(f"<-- Token check failed with status {response.status_code}. Allowing request to proceed.")
                return True

    except httpx.RequestError as e:
        print(f"Could not connect to token check API: {e}. Allowing request to proceed.")
        return True