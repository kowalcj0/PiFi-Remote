#!/usr/bin/python
import os 
import signal
import sys
import logging
from time import sleep

from evdev import InputDevice, categorize, ecodes
import mpd
            
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s',
                    filename='/var/log/pifi-remote.log',
                    filemode='w')

def exitHandler(signal, frame):
    logging.info("Signaling internal jobs to stop...")
    try:
        os.system("mpc stop")
        stopExternalStreaming()
    except:
        logging.error("Unexpected error: %s", sys.exc_info()[0])
        
def stopExternalStreaming():
    os.system("killall -SIGUSR2 shairport")

def createMPDClient():
    mpc = mpd.MPDClient()           
    mpc.timeout = None              # network timeout in seconds (floats allowed), default: None
    mpc.idletimeout = None          # timeout for fetching the result of the idle command is handled seperately, default: None
    mpc.connect("localhost", 6600)  # connect to localhost:6600
    #mpc.random(0)
    mpc.consume(0)
    mpc.single(0)
    #mpc.repeat(1)
    mpc.crossfade(1)
    return mpc
    
def monitorRemote():
    dev = InputDevice('/dev/input/event0')
    logging.info("Job monitorRemote started")
    for event in dev.read_loop():
        #logging.debug(str(categorize(event)))
        if event.type != ecodes.EV_KEY or event.value != 1:
            sleep(0.05)
            continue
        try:
            mpc = createMPDClient()
            status = mpc.status()
            logging.debug("Status: {}".format(status))
            logging.debug("KeyCode: {}".format(event.code))
            if event.code in [ecodes.KEY_LEFT, 165]:
                mpc.previous()
            elif event.code in [ecodes.KEY_RIGHT, 163]:
                mpc.next()
            elif event.code in [ecodes.KEY_UP, 115]:
                mpc.setvol(int(status['volume'])+1)
            elif event.code in [ecodes.KEY_DOWN, 114]:
                mpc.setvol(int(status['volume'])-1)
            elif event.code == 168:
                mpc.seekcur(-5)
            elif event.code == 208:
                mpc.seekcur('+5')
            elif event.code == 43:
                if int(status['repeat']) == 0:
                    mpc.repeat(1)
                else:
                    mpc.repeat(0)
            elif event.code == 20:
                if status['random'] == '0':
                    mpc.random(1)
                else:
                    mpc.random(0)
            elif event.code in [ecodes.KEY_ENTER, 164]:
                if status['state'] == 'play':
                    mpc.pause()
                else:
                    stopExternalStreaming()
                    mpc.play()
            elif event.code in [ecodes.KEY_ESC, 166]:
                stopExternalStreaming()
                mpc.stop()
                os.system("mpc volume -1")
                os.system("mpc volume +1")
            elif event.code == ecodes.KEY_A:
                break
            mpc.close() 
            mpc.disconnect()
        except Exception as e:
            logging.error("Caught exception: %s (%s)", e , type(e)) 
    logging.info("Job monitorRemote stopped")

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
        monitorRemote()
    except Exception as e:
        logging.error("Critical exception: %s", e)

    logging.info("terminated")     
    exit(0)
    
if __name__ == '__main__':
    main()
