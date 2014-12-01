#!/usr/bin/python
import threading
import logging
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from WaitForMultipleEvents import WaitForMultipleEvents

"""
Pi screen LCD 16x2 
"""
class LCD16x2(object):
    mLcd = None
    mUpdate1 = threading.RLock()
    mUpdate2 = threading.RLock()
    
    @classmethod
    def init(cls, lcd):
        cls.mLcd = lcd
    
    @classmethod
    def terminate(cls):
        cls.mLcd = None
        
    @classmethod
    def switchOn(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.RED)
    
    @classmethod
    def switchOff(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.OFF)
    
    @classmethod
    def setText(cls, id, text, delay = 0):
        with cls.mLock:
            if len(text) > 16:
                text = text[0:15]
            else:
                text += " "*(16-len(text))
            if id == 1 and cls.mD1 == 0:
                cls.mStr1 = text
                cls.mD1 = delay
                cls.mController.set(cls.mUpdate1)
            elif id == 2 and cls.mD2 == 0:
                cls.mStr2 = text
                cls.mD2 = delay
                cls.mController.set(cls.mUpdate2)
    
    @classmethod
    def getText(cls, id):
        with cls.mLock:
            if id == 1:
                line = cls.mStr1
                delay = cls.mD1
                cls.mStr1 = ''
                cls.mD1 = 0
                cls.mController.clear(cls.mUpdate1)
            elif id == 2:
                line = cls.mStr2
                delay = cls.mD2
                cls.mStr2 = ''
                cls.mD2 = 0
                cls.mController.clear(cls.mUpdate2)
        return (line, delay)
    
    @classmethod
    def timerEnds(cls, disableEvent, timers, index):
        disableEvent.clear()
        timers[index] = None
    
    @classmethod
    def display(cls): 
        freeze1 = threading.Event()
        freeze2 = threading.Event()
        timers = [None, None]
        logging.info("Job LCD display started")
        while not cls.mStop.is_set():
            line1 = ''
            line2 = ''
            triggeredEvents = cls.mController.waitAny()
            if cls.mUpdate1.is_set():
                (line1, d1) = cls.getText(1)      
                #logging.debug("New line1: %s", line1)
                if d1 > 0 and len(line1) > 0:
                    if timers[0] is not None:
                        timers[0].cancel()
                    freeze1.set()
                    timers[0] = threading.Timer(d1, cls.timerEnds, args=[freeze1,timers,0])
                    timers[0].start()
                if timers[1] is not None:
                    timers[1].cancel()
                    timers[1] = None
                    freeze2.clear()
            if not freeze2.is_set() and cls.mUpdate2.is_set():
                (line2, d2) = cls.getText(2)  
                if d2 > 0 and len(line2) > 0:
                    #logging.debug("New line2: %s - %d", line2, cls.mD2)
                    if timers[1] is not None:
                        timers[1].cancel()
                    freeze2.set()
                    timers[1] = threading.Timer(d2, cls.timerEnds, args=[freeze2,timers,1])
                    timers[1].start()       
            with cls.mLock:
                if line1 != '':  
                    #logging.debug("msg:%s / %s", line1, line2)
                    cls.mLcd.clear()
                cls.mLcd.message(line1 + '\n' + line2)
        logging.info("Job LCD display stopped")
        
        
"""
Pi screen LCD 16x2 
"""
class LCD16x2t(object):
    mLcd = None
    mStop = None
    mLock = None
    mThread = None
    mController = None
    mUpdate1 = threading.Event()
    mUpdate2 = threading.Event()
    mStr1 = ''
    mStr2 = ''
    mD1 = 0
    mD2 = 0
    
    @classmethod
    def init(cls, lcd, stopEvent):
        cls.mStop = stopEvent
        cls.mLcd = lcd
        cls.mController = WaitForMultipleEvents([cls.mUpdate1, cls.mUpdate2, cls.mStop])
        cls.mLock = threading.Lock()
        cls.mThread = threading.Thread(target=cls.display)
        cls.mThread.start()
        
    @classmethod
    def terminate(cls):
        cls.mStop.set()
        if cls.mThread:
            cls.mThread.join()
            cls.mThread = None
        
    @classmethod
    def switchOn(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.RED)
    
    @classmethod
    def switchOff(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.OFF)
    
    @classmethod
    def setText(cls, id, text, delay = 0):
        with cls.mLock:
            if len(text) > 16:
                text = text[0:15]
            else:
                text += " "*(16-len(text))
            if id == 1 and cls.mD1 == 0:
                cls.mStr1 = text
                cls.mD1 = delay
                cls.mController.set(cls.mUpdate1)
            elif id == 2 and cls.mD2 == 0:
                cls.mStr2 = text
                cls.mD2 = delay
                cls.mController.set(cls.mUpdate2)
    
    @classmethod
    def getText(cls, id):
        with cls.mLock:
            if id == 1:
                line = cls.mStr1
                delay = cls.mD1
                cls.mStr1 = ''
                cls.mD1 = 0
                cls.mController.clear(cls.mUpdate1)
            elif id == 2:
                line = cls.mStr2
                delay = cls.mD2
                cls.mStr2 = ''
                cls.mD2 = 0
                cls.mController.clear(cls.mUpdate2)
        return (line, delay)
    
    @classmethod
    def timerEnds(cls, disableEvent, timers, index):
        disableEvent.clear()
        timers[index] = None
    
    @classmethod
    def display(cls): 
        freeze1 = threading.Event()
        freeze2 = threading.Event()
        timers = [None, None]
        logging.info("Job LCD display started")
        while not cls.mStop.is_set():
            line1 = ''
            line2 = ''
            triggeredEvents = cls.mController.waitAny()
            if cls.mUpdate1.is_set():
                (line1, d1) = cls.getText(1)      
                #logging.debug("New line1: %s", line1)
                if d1 > 0 and len(line1) > 0:
                    if timers[0] is not None:
                        timers[0].cancel()
                    freeze1.set()
                    timers[0] = threading.Timer(d1, cls.timerEnds, args=[freeze1,timers,0])
                    timers[0].start()
                if timers[1] is not None:
                    timers[1].cancel()
                    timers[1] = None
                    freeze2.clear()
            if not freeze2.is_set() and cls.mUpdate2.is_set():
                (line2, d2) = cls.getText(2)  
                if d2 > 0 and len(line2) > 0:
                    #logging.debug("New line2: %s - %d", line2, cls.mD2)
                    if timers[1] is not None:
                        timers[1].cancel()
                    freeze2.set()
                    timers[1] = threading.Timer(d2, cls.timerEnds, args=[freeze2,timers,1])
                    timers[1].start()       
            with cls.mLock:
                if line1 != '':  
                    #logging.debug("msg:%s / %s", line1, line2)
                    cls.mLcd.clear()
                cls.mLcd.message(line1 + '\n' + line2)
        logging.info("Job LCD display stopped")