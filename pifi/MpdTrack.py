#!/usr/bin/python
import threading
import logging
from mpd import MPDClient

class MpdTrack(object):
    mMpc = None
    mMessage = None
    mLock = threading.Lock()
    
    @classmethod
    def init(cls, mpc):
        cls.mMpc = mpc

    @classmethod
    def getInfo(cls):
        with cls.mLock:
            return cls.mMessage
        
    @classmethod
    def retrieve(cls):
        msg = None
        status = cls.mMpc.status()
        state = status['state']
        if state in ['play', 'pause']:        
            current = cls.mMpc.currentsong()
            filename = current['file']
            if filename.startswith('http://'):
                if 'name' in current.keys():
                    item1 = current['name']
                else:
                    item1 = current['file']
                if state == 'pause':
                    item2 = '[paused]'
                else:
                    item2 = ''
            else:
                if 'title' in current.keys():
                    item1 = current['title']
                else:
                    item1 = current['file']
                if state == 'pause':
                    elapsed = str(int(float(status['elapsed'])))
                    logging.debug("Elapsed: %s", elapsed)
                    item2 = '[paused]'
                elif 'artist' in current.keys():
                    item2 = current['artist']
                else:
                    item2 = ''
            msg = [item1, item2]
        with cls.mLock:
            cls.mMessage = msg
        return msg
        
        