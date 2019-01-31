from setuptools import setup

APP = ['radiobar.py']
APP_NAME = "RadioBar"
APP_VERSION = "0.1"
DATA_FILES = ['channels.json','remote.py','radio-icon-grey.png','radio-icon.png']
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'radiobar.icns',
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "Listen to radio in your menubar",
        'CFBundleIdentifier': "com.mdbraber.radiobar",
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'LSUIElement': True,
    },
    'packages': ['rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
