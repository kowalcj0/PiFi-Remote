#!/usr/bin/python
import os 
import signal
import sys
import threading
import logging
from time import sleep

import audioop
import mpd

from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from PiScreens import LCD16x2
from MpdTrack import MpdTrack
            
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s',
                    filename='/var/log/pifi-display.log',
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
            logging.info("Level= %f %f %f %f", rms, level1, level2, level)
    except Exception as e:
        logging.error("%s (%s)", e , type(e))  
    return level
                        
def refreshRMS(changeEvent, stopEvent):
    MPD_FIFO = '/tmp/mpd.fifo'
    logging.info("Job refreshRMS started")
    try:
        with open(MPD_FIFO) as fifo:
            while not stopEvent.is_set():
                if MpdTrack.getInfo() is not None:
                    n = computeRMS(fifo, 2024, 16)
                    LCD16x2.setLine2("="*n + " "*(16-n))
                    sleep(0.01)
    except Exception as e:
        logging.critical("Critical exception: %s (%s)", e , type(e))
    logging.info("Job refreshRMS stopped")

def refreshRMS2(changeEvent, stopEvent):
    import SpectrumAnalyzer as sa
    logging.info("Job refreshRMS started")
    try:
        analyzer = sa.SpectrumAnalyzer(1024, 44100, 8, 5)
        with open(sa.MPD_FIFO) as fifo:
            while not stopEvent.is_set():
                if changeEvent.is_set():
                    analyzer.resetSmoothing()
                    changeEvent.clear()
                if MusicTrack.getInfo() is not None:
                    n = analyzer.computeRMS(fifo, 16)
                    LCD16x2.setLine2("="*n + " "*(16-n))
                    sleep(0.01)
    except Exception as e:
        logging.critical("Critical exception: %s (%s)", e , type(e))
    logging.info("Job refreshRMS stopped")

def monitorShairportMetadata(changeEvent, stopEvent):
    SHAIRPORT_FIFO = '/tmp/shaiport/now_playing'
    logging.info("Job monitorShairportMetadata started")
    try:
        with open(SHAIRPORT_FIFO) as fifo:
            while not stopEvent.is_set() and not changeEvent.is_set():
                line = fifo.read()
                if line:
                    LCD16x2.setLine1(line, 0.1)
    except Exception as e:
        logging.critical("Critical exception: %s (%s)", e , type(e))
    logging.info("Job monitorShairportMetadata stopped")

def refreshTrack(changeEvent, stopEvent):
    mpc = createMPDClient()
    MpdTrack.init(mpc)
    prevTrack = None
    threadShairport = None
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
                        os.system("killall -SIGUSR2 shairport")
                        if threadShairport is not None:
                            threadShairport.join()
                            threadShairport = None
                        LCD16x2.switchOn()
                        LCD16x2.setLine1(track[0], 0)
                    if prevTrack is None or track[1] != prevTrack[1]:
                        LCD16x2.setLine2(track[1]+" "*(16-len(track[1])), 1)
                    prevTrack = track
                else:
                    LCD16x2.switchOff()
                    prevTrack = None
                    threadShairport = threading.Thread(target=monitorShairportMetadata, args=(changeEvent, mStop))
            elif subsystem == 'mixer':
                status = mpc.status()
                logging.info("Volume change: %s", status['volume'])
                if status['state'] != 'stop':
                    LCD16x2.setLine2("Volume {0!s}%       ".format(status['volume']), 0.5)
        except mpd.ConnectionError as e:
            logging.error("Connection error: %s", e)
            mpc.connect("localhost", 6600)
        except Exception as e:
            logging.critical("Critical exception: %s (%s)", e , type(e))
            mpc = createMPDClient()
            MpdTrack.init(mpc)
    mpc.close()
    mpc.disconnect() 
    logging.info("Job refreshTrack stopped")
    
def startJobs():
    global mChangeEvent
    global mStop
    global mThreadTrack
    global mThreadRMS

    mStop = threading.Event()
    mChangeEvent = threading.Event()
    
    # Use busnum = 0 for raspi version 1 (256MB) and busnum = 1 for version 2
    lcd = Adafruit_CharLCDPlate(busnum = 1) 
    LCD16x2.init(lcd, mStop)
    LCD16x2.switchOn()
    LCD16x2.setLine1("Welcome to PiFi\nyour music hub!") 
    
    logging.info("RMS display job starting...")
    mThreadRMS = threading.Thread(target=refreshRMS, args=(mChangeEvent, mStop))
    mThreadRMS.start()
    
    sleep(1)
    LCD16x2.switchOff()
    
    logging.info("Track display job starting...")
    refreshTrack(mChangeEvent, mStop)

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
    
    LCD16x2.switchOff()
    
    mChangeEvent = None
    mStop = None
    logging.info("Jobs stopped.")

def main():
    logging.info("starting %s", __file__)  
    signal.signal(signal.SIGINT, exitHandler)
    signal.signal(signal.SIGTERM, exitHandler)
    
    mpc = createMPDClient()
    logging.info("mpd version: %s", mpc.mpd_version)
    logging.info("mpd outputs: %s", str(mpc.outputs()))
    logging.info("mpd stats: %s", str(mpc.stats()))
    mpc.close()
    mpc.disconnect()
    mpc = None
    
    try:
        startJobs()
    except Exception as e:
        logging.error("Critical exception: %s", e)
        
    stopJobs()
    logging.info("terminated")      
    exit(0)
    
if __name__ == '__main__':
    main()