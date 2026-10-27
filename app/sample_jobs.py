"""Slow file processing runs off the controller/timing thread."""
from concurrent.futures import ThreadPoolExecutor
import copy


class SampleJobs:
    def __init__(self):self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sample-edit');self.pending=[]
    def submit(self,kind,target,track,function,*args):
        if self.pending:return False
        self.pending.append((kind,target,copy.deepcopy(track),self.worker.submit(function,*args)));return True
    def poll(self):
        results=[]
        for item in list(self.pending):
            kind,target,track,future=item
            if not future.done():continue
            self.pending.remove(item)
            try:results.append((kind,target,track,future.result(),None))
            except Exception as error:results.append((kind,target,track,None,error))
        return results
    def close(self):self.worker.shutdown(wait=True,cancel_futures=True)
