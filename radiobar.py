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

rumps.debug_mode(False)

if 'VLC_PLUGIN_PATH' not in os.environ:
    # print('VLC_PLUGIN_PATH not set. Setting now...')
    os.environ['VLC_PLUGIN_PATH'] = '$VLC_PLUGIN_PATH:/Applications/VLC.app/Contents/MacOS/plugins'

class RadioBarRemoteThread(threading.Thread):
    def __init__(self, radiobar, host, port):
        super(RadioBarRemoteThread, self).__init__()
        self.stop_event = threading.Event()

        self.radiobar = radiobar

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.socket.bind((self.host, self.port))
        self.socket.listen()

    def run(self):
        radiobar = self.radiobar
        while not self.stop_event.is_set():
            c, addr = self.socket.accept()
            data = c.recv(1024)
            msg = data.decode("utf-8")
            print("Remote received: " + msg)
            if msg == "":
                radiobar.toggle_playback(radiobar.menu[radiobar.active_station])
            elif msg.isnumeric() and 0 <= int(msg)-1 < len(radiobar.stations):
                radiobar.play(radiobar.menu[radiobar.stations[int(msg)-1]['title']])
                c.send(b'Listening to ' + radiobar.stations[int(msg)-1]['title'].encode('utf-8'))  
            elif msg == "off":
                radiobar.stop_playback(radiobar.menu["Stop"])
                c.send(b'Off')
            elif msg == "on" or msg == "resume":
                if radiobar.active_station:
                    radiobar.toggle_playback(radiobar.menu[radiobar.active_station])
                    c.send(b'On')
            elif msg == "pause":
                if radiobar.active_station:
                    radiobar.toggle_playback(radiobar.menu[radiobar.active_station])
                    c.send(b'Pause')
            elif msg == "info":
                nowplaying = radiobar.get_nowplaying()
                c.send(nowplaying.encode('utf-8'))
            elif msg == "toggle":
                radiobar.toggle_playback()
                c.send(b'Toggle ' + radiobar.active_station.encode('utf-8'))
            else:
                c.send(b'Unknown input')
        c.close()

    def stop(self):
        self.stop_event.set()

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
        # prevent multiple calls from sleep/wake
        self.awake = True

        self.threads = []
        remote_thread = RadioBarRemoteThread(self, '127.0.0.1', 65432)
        self.threads.append(remote_thread)
        remote_thread.start()

    def build_menu(self):
        self.menu.clear()

        if len(self.stations) < 1:
            rumps.alert('No stations loaded.')

        new_menu = []

        new_menu.append(rumps.MenuItem('Now Playing', callback=None))
        new_menu.append(rumps.separator)

        for station in self.stations:
            item = rumps.MenuItem(station['title'], callback=self.toggle_playback)
            new_menu.append(item)

        new_menu.append(rumps.separator)
        new_menu.append(rumps.MenuItem('Stop'))
        new_menu.append(rumps.separator)
        new_menu.append(rumps.MenuItem('Quit RadioBar',callback=self.quit))

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

    def start_radio(self):
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
        self.menu[self.active_station].set_callback(self.toggle_playback)
        self.active_station = None
        self.title = None
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
        print("Playing radio: " + sender.title)
        self.notify("Playing radio: " + sender.title)

        # reset Stop
        self.menu['Stop'].set_callback(self.stop_playback)
        self.menu['Stop'].title = 'Stop'

        self.icon = 'radio-icon.png'

        self.start_radio()

        time.sleep(.3)
        self.set_nowplaying(self.get_nowplaying())

    def stop_playback(self, sender):
        self.reset_menu_state()
        self.player.stop()
        self.menu['Now Playing'].title = 'Nothing playing...'
        self.icon = 'radio-icon-grey.png'
        self.notify("Stopped")

    def toggle_playback(self, sender):
        # Stopped -> Playing
        if sender == None:
            pass
        elif self.active_station is None and sender is not None:
            self.play(sender)
        elif self.menu[self.active_station] is not sender:
            self.play(sender)
        else: 
            active_menu = self.menu[self.active_station]
            # Playing -> Paused
            if active_menu.state == 1:
                active_menu.state = -1
                self.icon = 'radio-icon-grey.png'
                self.player.stop()
            # Paused -> Playing
            elif active_menu.state == -1:
                active_menu.state = 1
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

    def notify(self, msg):
        if msg != self.active_station:
            print("Notification: " + msg)
            if self.active_station:
                rumps.notification('RadioBar', self.active_station, msg)
            else:
                rumps.notification('RadioBar', msg, None)

    def quit(self, sender):
        for t in self.threads:
            t.stop()
        rumps.quit_application(sender)

    def sleep(self):
        print("Going to sleep!")
        if self.awake and self.active_station:
            self.toggle_playback(self.menu[self.active_station])
        self.awake = False
    
    def wake(self):
        print("Waking up!")
        self.awake = True

if __name__ == "__main__":
    RadioBar().run()
