"""Linux resource snapshots; slow filesystem probes run outside the UI thread."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import time

def core_page_count(stats, controller='mikro'):
    size=8 if controller=='mk2' else 4
    return (len(stats.get('cpu_cores',[]))+size-1)//size

def system_page_count(stats, controller='mikro'):
    # Summary/brand pages, per-core pages, then every storage page.
    return (1 if controller == 'mk2' else 2) + core_page_count(stats,controller) + max(1, (len(stats['storage']) + 1)//2)

def read_resources(root, sources, previous=None, proc=Path('/proc')):
    cpu=None;cores=[];current={}
    old=previous if isinstance(previous,dict) else {'cpu':previous} if previous else {}
    def utilization(key,values):
        total,idle=sum(values),values[3]+values[4];current[key]=(total,idle)
        before=old.get(key)
        if before and total>before[0] and idle>=before[1]:
            return max(0,min(100,100*(1-(idle-before[1])/(total-before[0]))))
        return None
    try:
        for line in (proc/'stat').read_text().splitlines():
            key,*parts=line.split()
            if key!='cpu' and not (key.startswith('cpu') and key[3:].isdigit()):continue
            values=list(map(int,parts[:8]))
            if len(values)<5:continue
            percent=utilization(key,values)
            if key=='cpu':cpu=percent
            else:cores.append(dict(id=int(key[3:]),percent=percent))
        cores.sort(key=lambda core:core['id'])
    except (OSError,ValueError,IndexError):pass
    ram = None
    try:
        values = {k: int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in (proc/'meminfo').read_text().splitlines())}
        total = values['MemTotal']; available = values['MemAvailable']
        if total > 0: ram = {'total': total, 'used': max(0, total-available), 'percent': max(0, min(100, 100*(total-available)/total))}
    except (OSError, ValueError, KeyError):
        pass
    disks = []
    for name, path in [('SD CARD', Path(root))] + [(s.name, s.path) for s in sources if s.name != 'SD CARD']:
        try:
            if not path.is_dir():continue
            usage = shutil.disk_usage(path)
            disks.append({'name': name, 'total': usage.total, 'used': usage.used, 'percent': 100*usage.used/usage.total if usage.total else 0})
        except OSError:
            continue
    return {'cpu': cpu, 'cpu_cores':cores, 'ram': ram, 'storage': disks}, current

class SystemMonitor:
    def __init__(self, root):
        self.root = root; self.previous = None; self.future = None; self.next_read = 0; self.active = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='system-info')
    def update(self, app, now=None):
        now = time.monotonic() if now is None else now
        if self.future is not None and self.future.done():
            try: app.system_stats, self.previous = self.future.result()
            except Exception: pass
            self.future = None
        active = app.page == 'SYSTEM'
        if active and not self.active:self.previous=None;self.next_read=0
        self.active=active
        if active and self.future is None and now >= self.next_read:
            self.future = self.pool.submit(read_resources, self.root, tuple(app.browser.sources), self.previous)
            self.next_read = now+1
    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
