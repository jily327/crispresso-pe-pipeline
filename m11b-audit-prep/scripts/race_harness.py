"""Deterministic test-side barriers, not candidate endpoints or production hooks."""
import asyncio,threading

class AsyncGate:
    def __init__(self,timeout=10):self.entered=asyncio.Event();self.release=asyncio.Event();self.timeout=timeout
    async def pause(self):
        self.entered.set();await asyncio.wait_for(self.release.wait(),self.timeout)
    async def call(self,fn,*args,after=False,**kwargs):
        if not after:await self.pause()
        value=await fn(*args,**kwargs)
        if after:await self.pause()
        return value

class ThreadGate:
    def __init__(self,timeout=10):self.entered=threading.Event();self.release=threading.Event();self.timeout=timeout
    def pause(self):
        self.entered.set()
        if not self.release.wait(self.timeout):raise TimeoutError('audit barrier not released')
    def wrap(self,fn,after=False):
        def held(*args,**kwargs):
            if not after:self.pause()
            value=fn(*args,**kwargs)
            if after:self.pause()
            return value
        return held
