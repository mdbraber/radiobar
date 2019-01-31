#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rumps
import ctypes
import os
import platform
import requests
import socket
import threading
import json
import time

# preload libvlccore.dylib
# https://github.com/oaubert/python-vlc/issues/37
d = '/Applications/VLC.app/Contents/MacOS/'
p = d + 'lib/libvlc.dylib'
if os.path.exists(p):
    # force pre-load of libvlccore.dylib  # ****
    ctypes.CDLL(d + 'lib/libvlccore.dylib')  # ****
    dll = ctypes.CDLL(p)

import vlc

#print(vlc.__file__)

rumps.debug_mode(True)
print(rumps.__file__)

if 'VLC_PLUGIN_PATH' not in os.environ:
    # print('VLC_PLUGIN_PATH not set. Setting now...')
    os.environ['VLC_PLUGIN_PATH'] = '$VLC_PLUGIN_PATH:/Applications/VLC.app/Contents/MacOS/plugins'

class RadioBar(rumps.App):

    def __init__(self):
        super(RadioBar, self).__init__('RadioBar',icon='radio-icon-grey.png', template=None, quit_button=None)

        self.show_notifications = True
        self.show_station = True
        
        self.active_station = None
        self.nowplaying = None
        self.player = vlc.MediaPlayer()
        self.stations = []
        self.urls = {}
        self.get_stations()

        t_socket = threading.Thread(target=self.listen_socket)
        t_socket.start()

    def build_menu(self):
        self.menu.clear()

        if len(self.stations) < 1:
            rumps.alert('No stations loaded.')

        new_menu = []

        new_menu.append(rumps.MenuItem('Now Playing', callback=None))
        new_menu.append(rumps.separator)

        for station in self.stations:
            item = rumps.MenuItem(station['title'], callback=self.play)
            new_menu.append(item)

        new_menu.append(rumps.separator)
        new_menu.append(rumps.MenuItem('Pause'))
        new_menu.append(rumps.MenuItem('Stop'))
        new_menu.append(rumps.separator)
        new_menu.append(rumps.MenuItem('Quit RadioBar',callback=rumps.quit_application))

        self.menu = new_menu

    def get_stations(self):
        if len(self.stations) > 0:
            return

        try:
            with open('channels.json') as json_data:
                j = json.load(json_data)
                for c in j['channels']:
                    self.stations.append(c)
                    self.urls[c['title']] = c['url']
        except requests.exceptions.RequestException as e:
            rumps.alert(e)

        self.build_menu()

    def play_radio(self):
        # craft station url
        station_url = self.urls[self.active_station]
        print(u'Playing URL %s' % station_url)

        # feed url to player
        self.player.set_mrl(station_url)
        self.player.play()
       
    def reset_menu_state(self):
        if self.active_station is None:
            return
        self.menu[self.active_station].state = 0
        self.menu[self.active_station].set_callback(self.play)
        self.active_station = None
        self.title = None
        self.menu['Pause'].state = 0
        self.menu['Pause'].title = 'Pause'
        self.menu['Pause'].set_callback(None)
        self.menu['Stop'].state = 0
        self.menu['Stop'].title = 'Stop'
        self.menu['Stop'].set_callback(None)
        self.icon = 'radio-icon-grey.png'

    def play(self, sender):
        # is there already a station playing or a paused station?
        if self.active_station is not None and self.menu[self.active_station].state is not 0:
            self.reset_menu_state()

        self.active_station = sender.title
        self.title = ' ' + sender.title
        sender.state = 1
        sender.set_callback(None)
        print("Playing radio: " + sender.title)
        self.notify("Playing radio: " + sender.title)

        # reset Pause
        self.menu['Pause'].set_callback(self.toggle_playback)
        self.menu['Pause'].title = 'Pause'

        # reset Stop
        self.menu['Stop'].set_callback(self.stop_playback)
        self.menu['Stop'].title = 'Stop'

        self.icon = 'radio-icon.png'

        self.play_radio()

        time.sleep(.3)
        self.set_nowplaying(self.get_nowplaying())

    def stop_playback(self, sender):
        #sender.state = 1
        self.reset_menu_state()
        self.player.stop()
        self.menu['Now Playing'].title = 'Nothing playing...'
        self.icon = 'radio-icon-grey.png'
        self.notify("Stopped")

    def toggle_playback(self, sender):
        if self.active_station is not None:
            active_menu = self.menu[self.active_station]
            if active_menu.state == 1:
                active_menu.state = -1
                sender.title = 'Paused - click to resume'
                sender.state = 1
                self.icon = 'radio-icon-grey.png'
                self.player.pause()
            else:
                active_menu.state = 1
                sender.title = 'Pause'
                sender.state = 0
                self.icon = 'radio-icon.png'
                self.player.play()

    def get_nowplaying(self):

        if self.active_station is not None:
            media = self.player.get_media()
            try:
                media.parse_with_options(vlc.MediaParseFlag.network, 0)
                title = media.get_meta(vlc.Meta.Title)
                artist = media.get_meta(vlc.Meta.Artist)
                nowplaying = media.get_meta(vlc.Meta.NowPlaying)

                if artist and artist != "" and title and title != "":
                    return artist + " - " + title
                elif nowplaying and nowplaying != "":
                    return nowplaying
                elif self.active_station != "":
                    return self.active_station
                else:
                    return "Nothing playing..."
            except AttributeError as e:
                return None

    def set_nowplaying(self, nowplaying):
        self.nowplaying = nowplaying
        self.menu['Now Playing'].title = nowplaying
        #print("Now playing: " + nowplaying)
        self.notify(nowplaying)

    @rumps.timer(10)
    def track_metadata_changes(self, sender):
        nowplaying_new = self.get_nowplaying()
        if self.active_station and nowplaying_new and (self.nowplaying is None or nowplaying_new != self.nowplaying):
            self.set_nowplaying(nowplaying_new)

    def listen_socket(self):
        HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
        PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen()

        self.socket = s

        while True:
            c, addr = s.accept()
            data = c.recv(1024)
            msg = data.decode("utf-8")
            print("Received: " + msg)
            if msg.isnumeric() and 0 <= int(msg)-1 < len(self.stations):
                self.play(self.menu[self.stations[int(msg)-1]['title']])
                c.send(b'Listening to ' + self.stations[int(msg)-1]['title'].encode('utf-8'))  
            elif msg == "off":
                self.stop_playback(self.menu["Stop"])
                c.send(b'Off')
            elif msg == "info":
                nowplaying = self.get_nowplaying()
                c.send(nowplaying.encode('utf-8'))
            elif msg == "toggle":
                self.toggle_playback(self.menu['Pause'])
                c.send('Toggle ' + self.menu[self.active_station])
            elif msg == "icon":
                self.change_icon()
                c.send(b'Changed icon')
            else:
                c.send(b'Unknown input')
        c.close()

    def change_icon(self):
        self.title = 'Test'
        self.icon = 'radio-icon-red.png'

    def notify(self, msg):
        print("Notification: " + msg)
        if self.active_station:
            rumps.notification('RadioBar', self.active_station, msg)
        else:
            rumps.notification('RadioBar', msg, None)
        pass

    def quit(self):
        self.quit_application()
        self.socket.close()

    def sleep(self):
        print("Going to sleep!")
        self.stop_playback(None)

    def wake(self):
        print("Waking up!")

if __name__ == "__main__":
    RadioBar().run()
