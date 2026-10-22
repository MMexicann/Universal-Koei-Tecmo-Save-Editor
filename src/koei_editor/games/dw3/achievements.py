"""Steam achievement source mapping for the Remastered Steam edition."""
from koei_editor.shared.steam_achievements import fetch_steam_achievements


STEAM_APP_ID = 3841510
STEAM_STORE_URL = 'https://store.steampowered.com/app/3841510/DYNASTY_WARRIORS_3_Complete_Edition_Remastered/'


def fetch_achievements(api_key, steam_id64, **kwargs):
    """Fetch Steam states for this exact edition without retaining credentials."""
    return fetch_steam_achievements(api_key, steam_id64, STEAM_APP_ID, **kwargs)
