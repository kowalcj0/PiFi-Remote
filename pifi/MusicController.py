#!/usr/bin/python
import os 
import signal
import sys
import threading
import logging
from time import sleep
from evdev import InputDevice, categorize, ecodes
import mpd

from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from LCDScreen import LCDScreen
from MusicTrack import MusicTrack

import audioop
import errno
import math
#import SpectrumAnalyzer as sa
            
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s',
                    filename='/var/log/pifi.log',
                    filemode='w')

def exitHandler(signal, frame):
    logging.info("Signaling internal jobs to stop...")
    try:
        mStop.set()
        os.system("mpc stop")
    except:
        logging.error("Unexpected error: %s", sys.exc_info()[0])

def createMPDClient():
    mpc = mpd.MPDClient()           
    mpc.timeout = None              # network timeout in seconds (floats allowed), default: None
    mpc.idletimeout = None          # timeout for fetching the result of the idle command is handled seperately, default: None
    mpc.connect("localhost", 6600)  # connect to localhost:6600
    mpc.random(0)
    mpc.consume(0)
    mpc.single(0)
    mpc.repeat(1)
    mpc.crossfade(1)
    return mpc

def computeRMS(fifoFile, scaleWidth):
    while True:
        try:
            rawSamples = fifoFile.read(1024) 
        except OSError as err:
            if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                rawSamples = None
                logging.debug("AGAIN/WOULDBLOCK: %s", err)
            else:
                logging.error("%s", err)
        if rawSamples:
            logging.debug("stream: len=%d", len(rawSamples))
            #leftChannel = audioop.tomono(rawStream, 2, 1, 0)
            #rightChannel = audioop.tomono(rawStream, 2, 0, 1)
            #stereoPeak = audioop.max(rawStream, 2)
            #leftPeak = audioop.max(leftChannel, 2)
            #rightPeak = audioop.max(rightChannel, 2)
            #leftDB = 20 * math.log10(leftPeak) -74
            #rightDB = 20 * math.log10(rightPeak) -74
                        
def refreshRMS(changeEvent, stopEvent):
    MPD_FIFO = '/tmp/mpd.fifo'
    #analyzer = sa.SpectrumAnalyzer(1024, 44100, 1, 1)
    logging.info("Job refreshRMS started")
    with open(MPD_FIFO) as fifo:
        while not stopEvent.is_set():
            if changeEvent.is_set():
                #analyzer.resetSmoothing()
                changeEvent.clear()
            if MusicTrack.getInfo() is not None:
                n = computeRMS(fifo, 16)
                LCDScreen.setLine2("="*n + " "*(16-n))
                sleep(0.1)
    logging.info("Job refreshRMS stopped")

def refreshTrack(changeEvent, stopEvent):
    mpc = createMPDClient()
    MusicTrack.init(mpc)
    prevTrack = None
    logging.info("Job refreshTrack started")
    while not stopEvent.is_set():
        try:
            subsystem = mpc.idle('player','mixer')[0]
            if subsystem == 'player':
                track = MusicTrack.retrieve()
                logging.info("Track: %s", track)
                if track is not None:
                    if prevTrack is None or track[0] != prevTrack[0]:
                        changeEvent.set()
                        LCDScreen.switchOn()
                        LCDScreen.setLine1(track[0], 0)
                    if prevTrack is None or track[1] != prevTrack[1]:
                        LCDScreen.setLine2(track[1]+" "*(16-len(track[1])), 1)
                    prevTrack = track
                else:
                    LCDScreen.switchOff()
                    prevTrack = None
            elif subsystem == 'mixer':
                status = mpc.status()
                logging.info("Volume change: %s", status['volume'])
                if status['state'] != 'stop':
                    LCDScreen.setLine2("Volume {0!s}%       ".format(status['volume']), 1)
        except Exception as e:
            logging.error("Caught exception: %s (%s)", e , type(e))
            #mpc.close()
            mpc.disconnect() 
            mpc = createMPDClient()
            MusicTrack.init(mpc)
    mpc.close()
    mpc.disconnect() 
    logging.info("Job refreshTrack stopped")
    
def monitorRemote():
    dev = InputDevice('/dev/input/event0')
    logging.info("Job monitorRemote started")
    for event in dev.read_loop():
        #logging.debug(str(categorize(event)))
        if event.type != ecodes.EV_KEY or event.value != 1:
            sleep(0.1)
            continue
        try:
            mpc = createMPDClient()
            status = mpc.status()
            logging.debug("Status: {}".format(status))
            if event.code == ecodes.KEY_LEFT:
                mpc.previous()
            elif event.code == ecodes.KEY_RIGHT:
                mpc.next()
            elif event.code == ecodes.KEY_UP:
                mpc.setvol(int(status['volume'])+2)
            elif event.code == ecodes.KEY_DOWN:
                mpc.setvol(int(status['volume'])-2)
            elif event.code == ecodes.KEY_ENTER:
                if status['state'] == 'play':
                    mpc.pause()
                else:
                    mpc.play()
            elif event.code == ecodes.KEY_ESC:
                if status['state'] == 'stop':
                    mpc.play()
                else:
                    mpc.stop()
            elif event.code == ecodes.KEY_A:
                break
            mpc.close()
            mpc.disconnect()
        except Exception as e:
            logging.error("Caught exception: %s (%s)", e , type(e)) 
    logging.info("Job monitorRemote stopped")
    
def startJobs():
    global mChangeEvent
    global mStop
    global mThreadTrack
    global mThreadRMS

    mStop = threading.Event()
    mChangeEvent = threading.Event()
    
    # Use busnum = 0 for raspi version 1 (256MB) and busnum = 1 for version 2
    lcd = Adafruit_CharLCDPlate(busnum = 0)
    
    LCDScreen.init(lcd, mStop)
    
    logging.info("Track display job starting...")
    mThreadTrack = threading.Thread(target=refreshTrack, args=(mChangeEvent, mStop))
    mThreadTrack.start()
    
    logging.info("RMS display job starting...")
    mThreadRMS = threading.Thread(target=refreshRMS, args=(mChangeEvent, mStop))
    mThreadRMS.start()
    
    logging.info("Jobs started...")
    sleep(1)
    LCDScreen.switchOff()

def stopJobs():
    global mChangeEvent
    global mStop
    global mThreadTrack
    global mThreadRMS
    
    # Redundant with signal handler
    mStop.set()
    
    logging.info("RMS display job stopping...")
    if mThreadRMS is not None:
        mThreadRMS.join(3)
    mThreadRMS = None
    
    logging.info("MPD display job stopping...")
    if mThreadTrack is not None:
        mThreadTrack.join(3)
    mThreadTrack = None
    
    LCDScreen.switchOff()
    
    mChangeEvent = None
    mStop = None
    logging.info("Jobs stopped.")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, exitHandler)
    signal.signal(signal.SIGTERM, exitHandler)
    
    mpc = createMPDClient()
    logging.info("mpd version: " + mpc.mpd_version)
    logging.info("mpd outputs: " + str(mpc.outputs()))
    logging.info("mpd stats: " + str(mpc.stats()))
    mpc.close()
    mpc.disconnect()
    mpc = None
    
    try:
        startJobs()
        monitorRemote()
    except Exception as e:
        logging.error("Critical exception: %s", e)
        
    stopJobs()

    print "Terminating musiccontroller."     
    exit(0)
    
