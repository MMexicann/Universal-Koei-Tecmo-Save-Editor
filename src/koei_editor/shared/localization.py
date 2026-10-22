"""Small explicit shell catalog. Game labels and technical evidence stay original."""

LANGUAGES = {'en': 'English', 'de': 'Deutsch'}

_EN = {
    'library': '‹ Game Library', 'converter': 'Save Converter',
    'comparison': 'Compare Saves', 'batch': 'Batch Converter', 'save_library': 'Save Library',
    'help': 'Help Center', 'compatibility': 'Compatibility Center', 'workflows': 'Guides',
    'editing_presets': 'Reusable Editing Presets', 'transfer': 'Transfer from Save Copy',
    'controller_profiles': 'Controller & Input Profiles',
    'research_import': 'Research Import', 'research_lab': 'Save Research Lab', 'workflow_builder': 'Workflow Builder',
    'editing_and_research': 'Editing and Research',
    'feedback': 'Feedback', 'validation': 'Game Validation', 'plugins': 'Plugins',
    'commands': 'Search games, tools, commands…  Ctrl+K', 'appearance': 'Appearance',
    'commands_short': 'Commands · Ctrl+K', 'library_short': '‹ Library',
    'shell_controls': 'Navigation', 'hide_shell_controls': 'Hide navigation',
    'commands_compact': 'Search…  Ctrl+K',
    'language_en': 'Use English', 'language_de': 'Use German (Deutsch)',
    'text_size_100': 'Text size 100%', 'text_size_120': 'Text size 120%', 'text_size_140': 'Text size 140%',
    'language': 'Language', 'text_size': 'Text size', 'choose': 'Choose your game',
    'open_editors': 'Open editors ({count})', 'pending': '{count} pending',
    'platform': 'Choose your platform', 'series': 'Series', 'find': 'Find a game',
    'clear': 'Clear filters', 'compact': 'Compact cards', 'open': 'Open Editor',
    'resume': 'Resume Editor', 'empty': 'No games match. Try another name or clear the filters.',
    'footer': 'Always work with a separate copy. Your game sessions stay open when you switch games.',
    'contact': 'Contact Mexican', 'hint': '{count} editors · {scope}. Search by game, edition, platform or feature. Enter opens a single match; Ctrl+F searches across platforms.',
    'palette_title': 'Command Palette', 'palette_search': 'Search games, tools and commands',
    'palette_hint': '↑ ↓ select · Enter open · Esc close · Ctrl+D favorite',
    'favorite': 'Toggle favorite', 'favorite_tag': 'Favorite', 'recent_tag': 'Recent workspace',
    'game': 'Game', 'tool': 'Tool', 'command': 'Command', 'plugin': 'Community plugin', 'palette_empty': 'No matching commands.',
    'results': '{count} results', 'theme_light': 'Use light appearance', 'theme_dark': 'Use dark appearance',
    'open_copy': 'Open save copy', 'save_copy': 'Save edited copy', 'save_as': 'Save As',
    'undo': 'Undo staged change', 'review': 'Review changes', 'search_fields': 'Search current workspace',
    'favorites': 'Favorites', 'recent': 'Recent workspaces',
}
_DE = {
    'library': '‹ Spielebibliothek', 'converter': 'Spielstand konvertieren',
    'comparison': 'Spielstände vergleichen', 'batch': 'Stapelkonvertierung', 'save_library': 'Spielstandbibliothek',
    'help': 'Hilfezentrum', 'compatibility': 'Kompatibilität', 'workflows': 'Anleitungen',
    'editing_presets': 'Wiederverwendbare Bearbeitungsvorlagen', 'transfer': 'Aus Spielstandkopie übertragen',
    'controller_profiles': 'Controller- und Eingabeprofile',
    'research_import': 'Forschungsimport', 'research_lab': 'Spielstand-Forschungslabor', 'workflow_builder': 'Ablaufeditor',
    'editing_and_research': 'Bearbeitung und Forschung',
    'feedback': 'Rückmeldung', 'validation': 'Spielprüfung', 'plugins': 'Erweiterungen',
    'commands': 'Spiele, Werkzeuge, Befehle suchen…  Strg+K', 'appearance': 'Darstellung',
    'commands_short': 'Befehle · Strg+K', 'library_short': '‹ Bibliothek',
    'shell_controls': 'Navigation', 'hide_shell_controls': 'Schließen',
    'commands_compact': 'Suchen…  Strg+K',
    'language_en': 'Englisch verwenden (English)', 'language_de': 'Deutsch verwenden',
    'text_size_100': 'Textgröße 100%', 'text_size_120': 'Textgröße 120%', 'text_size_140': 'Textgröße 140%',
    'language': 'Sprache', 'text_size': 'Textgröße', 'choose': 'Spiel auswählen',
    'open_editors': 'Offene Editoren ({count})', 'pending': '{count} ausstehend',
    'platform': 'Plattform auswählen', 'series': 'Reihe', 'find': 'Spiel suchen',
    'clear': 'Filter zurücksetzen', 'compact': 'Kompakte Karten', 'open': 'Editor öffnen',
    'resume': 'Editor fortsetzen', 'empty': 'Keine passenden Spiele. Suchbegriff ändern oder Filter zurücksetzen.',
    'footer': 'Immer mit einer separaten Kopie arbeiten. Beim Wechsel bleiben die Editoren geöffnet.',
    'contact': 'Mexican kontaktieren', 'hint': '{count} Editoren · {scope}. Nach Spiel, Edition, Plattform oder Funktion suchen. Eingabe öffnet einen einzelnen Treffer; Strg+F durchsucht alle Plattformen.',
    'palette_title': 'Befehlspalette', 'palette_search': 'Spiele, Werkzeuge und Befehle suchen',
    'palette_hint': '↑ ↓ auswählen · Eingabe öffnen · Esc schließen · Strg+D Favorit',
    'favorite': 'Favorit umschalten', 'favorite_tag': 'Favorit', 'recent_tag': 'Zuletzt geöffnet',
    'game': 'Spiel', 'tool': 'Werkzeug', 'command': 'Befehl', 'plugin': 'Community-Erweiterung', 'palette_empty': 'Keine passenden Befehle.',
    'results': '{count} Treffer', 'theme_light': 'Helle Darstellung verwenden', 'theme_dark': 'Dunkle Darstellung verwenden',
    'open_copy': 'Spielstandkopie öffnen', 'save_copy': 'Bearbeitete Kopie speichern', 'save_as': 'Speichern unter',
    'undo': 'Vorgemerkte Änderung rückgängig machen', 'review': 'Änderungen prüfen',
    'search_fields': 'Aktuellen Arbeitsbereich durchsuchen', 'favorites': 'Favoriten', 'recent': 'Zuletzt geöffnet',
}
CATALOGS = {'en': _EN, 'de': _DE}


def translate(key, language='en', **values):
    """Fall back to English for new keys; reject unknown keys during development."""
    return CATALOGS.get(language, _EN).get(key, _EN[key]).format(**values)
