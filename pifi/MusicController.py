#!/usr/bin/python
import os 
import signal
import sys
import threading
import logging
import audioop
from time import sleep

from evdev import InputDevice, categorize, ecodes
import mpd

from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from LCDScreen import LCDScreen
from MpdTrack import MpdTrack
            
logging.basicConfig(level=logging.INFO,
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

def computeRMS(fifoFile, sampleSize, scale):
    exponent = 8
    level = 0
    try:
        rawSamples = fifoFile.read(sampleSize) 
        if rawSamples and len(rawSamples) == sampleSize:
            rms = float(audioop.rms(rawSamples, 1))
            level1 = min(rms/256.0, 1.0)
            level2 = level1**exponent
            level = int(level2*scale*10**(exponent-3))
            #logging.info("Level= %f %f %f %f", rms, level1, level2, level)
    except Exception as e:
        logging.error("%s", e)    
    return level
                        
def refreshRMS(changeEvent, stopEvent):
    MPD_FIFO = '/tmp/mpd.fifo'
    logging.info("Job refreshRMS started")
    with open(MPD_FIFO) as fifo:
        while not stopEvent.is_set():
            if MpdTrack.getInfo() is not None:
                n = computeRMS(fifo, 2024, 16)
                LCDScreen.setLine2("="*n + " "*(16-n))
                sleep(0.01)
    logging.info("Job refreshRMS stopped")

def refreshRMS2(changeEvent, stopEvent):
    import SpectrumAnalyzer as sa
    analyzer = sa.SpectrumAnalyzer(1024, 44100, 8, 5)
    logging.info("Job refreshRMS started")
    with open(sa.MPD_FIFO) as fifo:
        while not stopEvent.is_set():
            if changeEvent.is_set():
                analyzer.resetSmoothing()
                changeEvent.clear()
            if MusicTrack.getInfo() is not None:
                n = analyzer.computeRMS(fifo, 16)
                LCDScreen.setLine2("="*n + " "*(16-n))
                sleep(0.01)
    logging.info("Job refreshRMS stopped")

def refreshTrack(changeEvent, stopEvent):
    mpc = createMPDClient()
    MpdTrack.init(mpc)
    prevTrack = None
    logging.info("Job refreshTrack started")
    while not stopEvent.is_set():
        try:
            subsystem = mpc.idle('player','mixer')[0]
            if subsystem == 'player':
                track = MpdTrack.retrieve()
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
        except mpd.ConnectionError as e:
            logging.error("Caught exception: %s (%s)", e , type(e))
            mpc.connect("localhost", 6600)
        except Exception as e:
            logging.error("Caught exception: %s (%s)", e , type(e))
            mpc.disconnect() 
            mpc.connect("localhost", 6600)
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
    lcd = Adafruit_CharLCDPlate(busnum = 1)
    
    LCDScreen.init(lcd, mStop)
    
    logging.info("RMS display job starting...")
    mThreadRMS = threading.Thread(target=refreshRMS, args=(mChangeEvent, mStop))
    mThreadRMS.start()
    
    sleep(1)
    LCDScreen.switchOff()
    
    logging.info("Track display job starting...")
    mThreadTrack = threading.Thread(target=refreshTrack, args=(mChangeEvent, mStop))
    mThreadTrack.start()
    
    logging.info("Jobs started...")

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

def main():
    logging.info("starting %s", __file__)  
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

    logging.info("terminated")      
    exit(0)

if __name__ == '__main__':
    main()
