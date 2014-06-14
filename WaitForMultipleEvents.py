#!/usr/bin/python
import threading

class WaitForMultipleEvents(object):
    def __init__(self, eventsToWatch): 
        self.mEvtController = threading.Event() 
        self.mEventsToWatch = eventsToWatch 
        self.mLock = threading.Lock()
     
    def Set(self, event): 
        if event in self.mEventsToWatch: 
            with self.mLock:
                event.set() 
                self.mEvtController.set() 
     
    def Clear(self, event): 
        if event in self.mEventsToWatch: 
            with self.mLock:
                event.clear() 
                self.mEvtController.clear() 
     
    def ClearAll(self):
        with self.mLock:
            for event in self.mEventsToWatch: 
                event.clear() 
            self.mEvtController.clear() 
     
    def WaitAny(self): 
        self.mEvtController.wait() 
        # TODO: fix weakness?
        with self.mLock:
            evtMatches = [e for e in self.mEventsToWatch if e.is_set()] 
        return evtMatches 
