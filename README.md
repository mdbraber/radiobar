## RadioBar

Basic macOS menubar app to play user-defined radio stations with help from [rumps](https://github.com/jaredks/rumps) and VLC. Forked from [RadioBar](https://github.com/wass3r/RadioBar) by [David May](https://github.com/wass3r)

## Installation

- Be sure to adapt `channels.json` to your needs. 
- "Now playing" integration is experimental and might not work as expected

Use the include `command.py` to send commands to a running RadioBar instance to change channels and switch on/off.

## Development

Make sure you have VLC installed, ie. `brew cask install vlc`.

Tested in Python 2.7.x and 3.x. To run, try:
1. `pip install -r requirements.txt`
2. `python radiobar.py`

To re-build the macOS app, run:
1. `rm -rf ./dist/ ./build/`
2. `python setup.py py2app`

## Bugs

- `parse_with_options` might not not be needing the second argument (`timeout`) in your version. You could remove it (not sure yet if it makes any difference). I'm still trying to implement a hook that watches for metadata changes for now playing. Tips welcome :-)

- To use it with the current VLC (>= 3.x) we need to preload the `libvlccore.dylib` as a workaround. See 
https://github.com/oaubert/python-vlc/issues/37 for more info.

## License
MIT
