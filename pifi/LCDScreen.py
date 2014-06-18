#!/usr/bin/python
import threading
from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from WaitForMultipleEvents import WaitForMultipleEvents

class LCDScreen(object):
    mLcd = None
    mIsOn = None
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
    def init(cls, lcd, stopEvent, isOn):
        cls.mIsOn = isOn
        cls.mStop = stopEvent
        cls.mLcd = lcd
        cls.mController = WaitForMultipleEvents([cls.mUpdate1, cls.mUpdate2, cls.mStop])
        cls.mLock = threading.Lock()
        cls.mThread = threading.Thread(target=cls.display)
        cls.mThread.start()
        cls.switchOn()
        cls.mLcd.message("Welcome to PiFi\nyour music hub!") 
        
    @classmethod
    def switchOn(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.RED)
            cls.mIsOn.set()
    
    @classmethod
    def switchOff(cls):
        with cls.mLock:
            cls.mLcd.clear()
            cls.mLcd.backlight(cls.mLcd.OFF)
            cls.mIsOn.clear()
    
    @classmethod
    def setLines(cls, string1, delay1, string2, delay2):
        with cls.mLock:
            cls.mStr1 = string1
            cls.mD1 = delay1
            cls.mStr2 = string2
            cls.mD2 = delay2
            cls.mUpdate1.set()
            cls.mController.set(cls.mUpdate2)
        
    @classmethod
    def setLine1(cls, string, delay = 0):
        with cls.mLock:
            if cls.mD1 == 0:
                cls.mStr1 = string
                cls.mD1 = delay
                cls.mController.set(cls.mUpdate1)
    
    @classmethod
    def getLine1(cls):
        with cls.mLock:
            line1 = cls.mStr1[0:15]
            cls.mStr1 = ''
            d1 = cls.mD1
            cls.mD1 = 0
            cls.mController.clear(cls.mUpdate1)
        return (line1, d1)
        
    @classmethod
    def setLine2(cls, string, delay = 0):
        with cls.mLock:
            if cls.mD2 == 0:
                cls.mStr2 = string
                cls.mD2 = delay
                cls.mController.set(cls.mUpdate2)
    
    @classmethod
    def getLine2(cls):
        with cls.mLock:
            line2 = cls.mStr2[0:15]
            cls.mStr2 = ''
            d2 = cls.mD2
            cls.mD2 = 0
            cls.mController.clear(cls.mUpdate2)
        return (line2, d2)
    
    @classmethod
    def timerEnds(cls, disableEvent, timers, index):
        disableEvent.clear()
        timers[index] = None
    
    @classmethod
    def display(cls): 
        freeze1 = threading.Event()
        freeze2 = threading.Event()
        timers = [None, None]
        print "Job LCD display started"
        while not cls.mStop.is_set():
            line1 = ''
            line2 = ''
            triggeredEvents = cls.mController.waitAny()
            if cls.mUpdate1.is_set():
                (line1, d1) = cls.getLine1()      
                #print "line1:", line1
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
                (line2, d2) = cls.getLine2()  
                if d2 > 0 and len(line2) > 0:
                    #print "line2:", line2, cls.mD2
                    if timers[1] is not None:
                        timers[1].cancel()
                    freeze2.set()
                    timers[1] = threading.Timer(d2, cls.timerEnds, args=[freeze2,timers,1])
                    timers[1].start()       
            with cls.mLock:
                if line1 != '':  
                    #print "msg:", line1, line2
                    cls.mLcd.clear()
                cls.mLcd.message(line1 + '\n' + line2)
        print "Job LCD display stopped"