#!/usr/bin/python
import os 
import signal
import sys
import threading
from time import sleep
from evdev import InputDevice, ecodes
from mpd import MPDClient

from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from LCDScreen import LCDScreen
from MusicTrack import MusicTrack
import SpectrumAnalyzer as sa

def exitHandler(signal, frame):
    print "Signaling internal jobs to stop..."
    try:
        mStop.set()
        os.system("mpc stop")
    except:
        print "Unexpected error:", sys.exc_info()[0]

def createMPDClient():
    mpc = MPDClient()           
    mpc.timeout = 3                 # network timeout in seconds (floats allowed), default: None
    mpc.idletimeout = None          # timeout for fetching the result of the idle command is handled seperately, default: None
    mpc.connect("localhost", 6600)  # connect to localhost:6600
    mpc.random(0)
    mpc.crossfade(3)
    return mpc
            
def getMPDStatus(name):
    mpc = createMPDClient()
    status = mpc.status()
    mpc.close()
    mpc.disconnect()
    return status[name]
    
def refreshRMS(changeEvent, stopEvent):
    global mEnableRMSEvent
    analyzer = sa.SpectrumAnalyzer(1024, 44100, 8, 5)
    print "Job refreshRMS started"
    with open(sa.MPD_FIFO) as fifo:
        while not stopEvent.is_set():
            if changeEvent.is_set():
                analyzer.resetSmoothing()
                changeEvent.clear()
            if MusicTrack.getInfo() is not None:
                n = analyzer.computeRMS(fifo, 16)
                LCDScreen.setLine2("="*n + " "*(16-n))
    print "Job refreshRMS stopped"

def refreshTrack(changeEvent, stopEvent):
    mpc = createMPDClient()
    MusicTrack.init(mpc)
    prevTitle = None
    prevVol = None
    print "Job refreshTrack started"
    while not stopEvent.is_set():
        try:
            mpc.idle()
        except:
            pass
        track = MusicTrack.retrieve()
        if track is not None and track[0] != prevTitle:
            changeEvent.set()
            LCDScreen.switchOn()
            LCDScreen.setLines(track[0], 0, track[1], 1)
            prevTitle = track[0]
            prevVol = track[2]
        if track is not None and track[0] == prevTitle:
            if prevVol == track[2]:
                LCDScreen.setLine2(track[1], 1)
            else:
                LCDScreen.setLine2("Volume {0!s}%      ".format(track[2]), 1)
            prevVol = track[2]
        elif track is None:
            LCDScreen.switchOff()
            prevTitle = None
            prevVol = None
    mpc.close()
    mpc.disconnect() 
    print "Job refreshTrack stopped"
    
def monitorButtons(lcd, stopEvent, isOn):
    pressing = False
    print "Job monitorButtons started"
    while not stopEvent.is_set():
        if (lcd.buttonPressed(lcd.LEFT)):
            if not pressing:
                os.system("mpc prev")
                pressing = True
        elif (lcd.buttonPressed(lcd.RIGHT)):
            if not pressing:
                os.system("mpc next")
                pressing = True
        elif (lcd.buttonPressed(lcd.UP)):
            if not pressing:
                os.system("mpc volume +2")
                vol = getMPDStatus('volume')
                LCDScreen.setLine2("Volume {0!s}%      ".format(vol), 1)
                pressing = True
        elif (lcd.buttonPressed(lcd.DOWN)):
            if not pressing:
                os.system("mpc volume -2")
                vol = getMPDStatus('volume')
                LCDScreen.setLine2("Volume {0!s}%      ".format(vol), 1)
                pressing = True
        elif (lcd.buttonPressed(lcd.SELECT)):
            if not pressing:
                pressing = True
                if isOn.is_set():
                    os.system("mpc stop")
                    isOn.clear()
                else:
                    os.system("mpc play")
                    isOn.set()
        else:
            pressing = False
        sleep(0.25)
    print "Job monitorButtons stopped"
    
def monitorRemote():
    dev = InputDevice('/dev/input/event0')
    print "Job monitorRemote started"
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY or event.value != 1:
            continue
        if event.code == ecodes.KEY_LEFT:
            os.system("mpc prev")
        elif event.code == ecodes.KEY_RIGHT:
            os.system("mpc next")
        elif event.code == ecodes.KEY_UP:
            os.system("mpc volume +2")
            vol = getMPDStatus('volume')
            LCDScreen.setLine2("Volume {0!s}%     ".format(vol), 1)
        elif event.code == ecodes.KEY_DOWN:
            os.system("mpc volume -2")
            vol = getMPDStatus('volume')
            LCDScreen.setLine2("Volume {0!s}%     ".format(vol), 1)
        elif event.code == ecodes.KEY_ENTER:
            os.system("mpc toggle")
        elif event.code == ecodes.KEY_ESC:
            if mIsOn.is_set():
                os.system("mpc stop")
                mIsOn.clear()
            else:
                os.system("mpc play")
                mIsOn.set()
        elif event.code == ecodes.KEY_A:
            break
    print "Job monitorRemote stopped"
    
def startJobs():
    global mChangeEvent
    global mStop
    global mIsOn
    global mThreadTrack
    global mThreadRMS
    global mThreadLCDButtons
    
    # Use busnum = 0 for raspi version 1 (256MB) and busnum = 1 for version 2
    lcd = Adafruit_CharLCDPlate(busnum = 0)
        
    mChangeEvent = threading.Event()
    mStop = threading.Event()
    mIsOn = threading.Event() 
    
    LCDScreen.init(lcd, mStop, mIsOn)
    sleep(2)
    
    print "MPD display job starting..."
    mThreadTrack = threading.Thread(target=refreshTrack, args=(mChangeEvent, mStop))
    mThreadTrack.start()
    
    print "RMS display job starting..."
    mThreadRMS = threading.Thread(target=refreshRMS, args=(mChangeEvent, mStop))
    mThreadRMS.start()
    
    print "LCD buttons monitor job starting..."
    mThreadLCDButtons = threading.Thread(target=monitorButtons, args=(lcd, mStop, mIsOn))
    mThreadLCDButtons.start()


def stopJobs():
    global mChangeEvent
    global mStop
    global mIsOn
    global mThreadTrack
    global mThreadRMS
    global mThreadLCDButtons
    
    # Redundant with signal handler
    mStop.set()
    
    print "LCD buttons monitor job stopping..."
    if mThreadLCDButtons is not None:
        mThreadLCDButtons.join(3)
    mThreadLCDButtons = None
    
    print "RMS display job stopping..."
    if mThreadRMS is not None:
        mThreadRMS.join(3)
    mThreadRMS = None
    
    print "MPD display job stopping..."
    if mThreadTrack is not None:
        mThreadTrack.join(3)
    mThreadTrack = None
    
    LCDScreen.switchOff()
    
    mChangeEvent = None
    mStop = None
    mIsOn = None
    print "Jobs stopped."
    
def transformAudio():
    import os
    import audioop
    import time
    import errno
    import math
    
    #Open the FIFO that MPD has created for us
    #This represents the sample (44100:16:2) that MPD is currently "playing"
    fifo = os.open('/tmp/mpd.fifo', os.O_RDONLY)
    
    while 1:
        try:
            rawStream = os.read(fifo, 1024)
        except OSError as err:
            if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                rawStream = None
            else:
                raise
        if rawStream:
            leftChannel = audioop.tomono(rawStream, 2, 1, 0)
            rightChannel = audioop.tomono(rawStream, 2, 0, 1)
            stereoPeak = audioop.max(rawStream, 2)
            leftPeak = audioop.max(leftChannel, 2)
            rightPeak = audioop.max(rightChannel, 2)
            leftDB = 20 * math.log10(leftPeak) -74
            rightDB = 20 * math.log10(rightPeak) -74
            print(rightPeak, leftPeak, rightDB, leftDB)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, exitHandler)
    signal.signal(signal.SIGTERM, exitHandler)
    
    mpc = createMPDClient()
    print "mpd version:", mpc.mpd_version
    print "mpd outputs:", mpc.outputs()
    print "mpd stats :", mpc.stats()
    mpc.close()
    mpc.disconnect()   
    
    try:
        startJobs()
        monitorRemote()
    except Exception as e:
        print "Caught exception:", e
       
    stopJobs()

    print "Terminating musiccontroller script."     
    exit(0)
    