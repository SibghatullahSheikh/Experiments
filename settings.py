# Default settings


# Allow to override the default settings
try:
    from private_settings import *
    print '[INFO] Loaded private settings'
except ImportError:
    print '[WARNING] Define your private settings in "private_settings.py"'
