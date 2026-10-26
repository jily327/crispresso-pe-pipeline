"""Test-side barriers; a delayed HTTP response is never mistaken for a paused worker."""
import threading

class Barrier:
    def __init__(self,name,timeout=20):
        self.name=name;self.timeout=timeout;self.arrived=threading.Event();self.release=threading.Event()
    def stop(self):
        self.arrived.set()
        if not self.release.wait(self.timeout):raise TimeoutError('Unreleased audit barrier: '+self.name)
    def wait(self):
        if not self.arrived.wait(self.timeout):raise TimeoutError('Unreached audit barrier: '+self.name)
    def proceed(self):self.release.set()
