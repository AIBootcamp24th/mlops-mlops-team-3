import requests
from src.config import settings

def send_slack_message(text: str) -> bool:
    """Sends a message to the configured Slack channel using the bot token."""
    token = settings.slack_bot_token
    channel_id = settings.slack_channel_id
    
    if not token or not channel_id:
        print("Warning: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set. Skipping notification.")
        return False
        
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "channel": channel_id,
        "text": text
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            print(f"Error sending Slack message: {result.get('error')}")
            return False
        return True
    except Exception as e:
        print(f"Exception while sending Slack message: {e}")
        return False

if __name__ == "__main__":
    # Test script
    import sys
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Test message from Python Slack Notifier"
    send_slack_message(f":rocket: {message}")
