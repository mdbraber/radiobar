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
import re

from AppKit import NSAttributedString
from PyObjCTools.Conversion import propertyListFromPythonCollection
from Cocoa import (NSFont, NSFontAttributeName, NSColor, NSForegroundColorAttributeName)

# preload libvlccore.dylib
# https://github.com/oaubert/python-vlc/issues/37
d = '/Applications/VLC.app/Contents/MacOS/'
p = d + 'lib/libvlc.dylib'
if os.path.exists(p):
    # force pre-load of libvlccore.dylib  # ****
    ctypes.CDLL(d + 'lib/libvlccore.dylib')  # ****
    dll = ctypes.CDLL(p)

import vlc

rumps.debug_mode(True)

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
            elif msg == "nowplaying":
                c.send(bytes(radiobar.nowplaying.encode('utf-8')))
            elif msg == "show":
                radiobar.notify(radiobar.nowplaying)
                c.send(bytes(radiobar.nowplaying.encode('utf-8')))
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
        self.show_notification_station_change = False
        self.show_nowplaying_menubar = True

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

    def set_title(self, title, red = 29/255, green = 185/255, blue = 84/255 , alpha = 1):
        self.title = title
        # This is hacky, but works
        # https://github.com/jaredks/rumps/issues/30
        if title is not None:
            color = NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)
            font = NSFont.menuBarFontOfSize_(0)
            attributes = propertyListFromPythonCollection({NSForegroundColorAttributeName: color, NSFontAttributeName: font}, conversionHelper=lambda x: x)
            string = NSAttributedString.alloc().initWithString_attributes_(' ' + title, attributes)
            self._nsapp.nsstatusitem.setAttributedTitle_(string)

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
        self.set_title(None)
        self.menu['Stop'].state = 0
        self.menu['Stop'].title = 'Stop'
        self.menu['Stop'].set_callback(None)
        self.icon = 'radio-icon-grey.png'

    def play(self, sender):
        # is there already a station playing or a paused station?
        if self.active_station is not None and self.menu[self.active_station].state is not 0:
            self.reset_menu_state()

        self.active_station = sender.title
        self.set_title(sender.title, 1, 1, 1, 0.4)
        self.icon = 'radio-icon-green.png'
        sender.state = 1
        self.menu['Stop'].set_callback(self.stop_playback)
        self.menu['Stop'].title = 'Stop'

        print("Switching to station: " + self.active_station)
        self.start_radio()

        time.sleep(.3)
        self.update_nowplaying()

        print("Playing: " + self.nowplaying)
        if self.show_notification_station_change:
            self.notify(self.nowplaying)

    def stop_playback(self, sender):
        self.reset_menu_state()
        self.player.stop()
        self.menu['Now Playing'].title = 'Nothing playing...'
        self.icon = 'radio-icon-grey.png'
        self.notify("Stopped")

    def toggle_playback(self, sender):
        # Stopped -> Playing
        if sender is not None:
            # Starting to play - not been playing before
            if self.active_station is None:
                self.play(sender)
            # Paused, but we want to play another station
            elif self.menu[self.active_station] is not sender:
                self.play(sender)
            # Paused and clicked the currently paused station
            else: 
                active_menu = self.menu[self.active_station]
                # Playing -> Paused
                if active_menu.state == 1:
                    self.pause(active_menu)
                # Paused -> Playing
                elif active_menu.state == -1:
                    self.play(active_menu)

    def pause(self, sender):
        sender.state = - 1
        self.set_title(self.active_station, 1, 1, 1, 0.4)
        self.icon = 'radio-icon-grey.png'
        self.nowplaying = None
        # We're really stopping (because it's live radio and we don't want to buffer)
        self.player.stop()

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

    def update_nowplaying(self):
        state = self.player.get_state()
        # Try to update information asap, even if vlc.State.Opening
        if self.active_station is not None and self.player.get_state() in {vlc.State.Playing, vlc.State.Opening}:
            old_info = self.nowplaying
            new = self.get_nowplaying()
            new_info = new.replace(self.active_station + " - ","")
            # Remove non-info like "TOPSONG: " (NPO Radio 2)
            new_info = new_info.replace("TOPSONG: ","")
            # Remove trailing station info like "De Nieuws BV - BNN-VARA"
            new_info = re.sub(r' - [A-Z-]*$', "", new_info)
            if new_info.isupper():
                # Fix ALL UPPERCASE strings (and some annyoing regressions)
                new_info = new_info.title()
                # Get rid of uninteresting info like "Franz Ferdinand - This Fire (3Fm Intro)"
                new_info = re.sub(r'\(3Fm .*\)', "", new_info)
        
            self.nowplaying = new_info
            self.menu['Now Playing'].title = new_info
  
            if new_info == self.active_station:
                self.set_title(new_info)
            else:
                if self.show_nowplaying_menubar:
                    self.set_title(self.active_station + ' - ' + new_info)
                # This depends on how your stations work, but for me the station changes back to "Station Name - Show Name" after a song
                # and I don't want notifications all the time the show name comes back on as Now Playing new_info...
                # So we only show notifications when the new info doesn't start with the station name.
                if not new.startswith(self.active_station):
                    self.notify(new_info)


    @rumps.timer(10)
    def track_metadata_changes(self, sender):
        self.update_nowplaying()
   
    def notify(self, msg):
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
            self.pause(self.menu[self.active_station])
        self.awake = False
    
    def wake(self):
        print("Waking up!")
        self.awake = True

if __name__ == "__main__":
    RadioBar().run()
