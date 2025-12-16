import re

def extract_link_info(link):
    """
    Extracts (source_identifier, message_id) from a Telegram link.
    Supports:
    - Private: https://t.me/c/1234567890/100 -> (-1001234567890, 100)
    - Public: https://t.me/channelname/100 -> ('channelname', 100)
    """
    link = link.strip()

    # Regex for Private Links (t.me/c/ID/MSG_ID)
    # ID is usually the channel ID without -100 prefix
    private_match = re.search(r't\.me/c/(\d+)/(\d+)', link)
    if private_match:
        chat_id_str = private_match.group(1)
        msg_id = int(private_match.group(2))

        # Telethon usually expects -100 for private channels/supergroups
        # If the ID provided is just digits (like 123456), we prepend -100
        full_chat_id = int(f"-100{chat_id_str}")
        return full_chat_id, msg_id

    # Regex for Public Links (t.me/USERNAME/MSG_ID)
    public_match = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)', link)
    if public_match:
        username = public_match.group(1)
        msg_id = int(public_match.group(2))
        return username, msg_id

    return None, None

# Tests
print(extract_link_info("https://t.me/c/1792375836/2324"))
print(extract_link_info("https://t.me/CodeXBotzSupport/43976"))
print(extract_link_info("t.me/c/123/1"))
print(extract_link_info("https://t.me/some_channel/99"))
print(extract_link_info("invalid link"))
