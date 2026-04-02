from garminconnect import Garmin
import garth
import json
import os
from datetime import date


# Where garth stores OAuth tokens
TOKENSTORE = os.path.expanduser("~/.garth")

# Today's date
today = date.today().isoformat()

def get_client():
    """Get authenticated Garmin client."""
    
    # If we have saved tokens, use them
    if os.path.exists(TOKENSTORE):
        print("Loading saved tokens...")
        try:
            client = Garmin()
            client.login(TOKENSTORE)
            print("Connected using saved tokens.\n")
            return client
        except Exception as e:
            print(f"Saved tokens failed ({e}), need to log in again...")
    
    # No saved tokens — do interactive login
    print("\nNo saved tokens found.")
    print("We'll log in interactively to avoid rate limiting.\n")


    email = input("Enter your Garmin email: ")
    password = input("Enter your Garmin password: ")
    
    try:
        client = Garmin(email, password)
        client.login()
        client.garth.dump(TOKENSTORE)
        print(f"\nTokens saved to {TOKENSTORE}")
        print("Future runs won't need your credentials.\n")
        return client
        
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print("\nIf you're still rate limited, wait 1-2 hours and try again.")
        print("Garmin's rate limit resets after a period of no attempts.")
        raise

def fetch_readiness_data(client, today):
    """Fetch the data we need for daily readiness."""
    data = {}
    
    fetches = [
        ("body_battery", lambda: client.get_body_battery(today)),
        ("sleep",        lambda: client.get_sleep_data(today)),
        ("hrv",          lambda: client.get_hrv_data(today)),
        ("stats",        lambda: client.get_stats(today)),
    ]
    
    for name, fetch_fn in fetches:
        try:
            print(f"Fetching {name}...")
            data[name] = fetch_fn()
            print(f"  Got {name}.")
        except Exception as e:
            print(f"  Could not fetch {name}: {e}")
            data[name] = None
    
    return data

# Main
print("=== Garmin Readiness Data ===\n")

try:
    client = get_client()
    data = fetch_readiness_data(client, today)
    
    print("\n=== Raw data ===")
    print(json.dumps(data, indent=2, default=str))
    
except Exception as e:
    print(f"\nFailed to connect: {e}")