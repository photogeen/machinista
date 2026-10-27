"""Small runtime snapshots: no project writes and no audio work in the renderer."""
import math


class RuntimeAudio:
    def __init__(self):
        self.transport_key = None
        self.transport_due = self.status_due = 0
        self.last_phase = -1
        self.watch = None
        self.latency_bus = None
        self.mixer_context = None

    def update(self, app, audio, now, next_tick):
        running = bool(app.playing and not app.count_remaining)
        phase = max(0, app.clock_phase)
        key = (app.project_generation, app.project['tempo'], running)
        discontinuity = phase < self.last_phase or abs(phase-self.last_phase) > 16
        if key != self.transport_key or discontinuity or running and now >= self.transport_due or not running and phase != self.last_phase:
            fraction = max(0, min(1, 1-(next_tick-now)/app.clock_interval())) if running and next_tick is not None else 0
            audio.command(f'transport {app.project["tempo"]} {int(running)} {(phase+fraction)/96:.9f} {now:.9f}')
            self.transport_key = key
            self.transport_due = now+.05
        self.last_phase = phase
        context=(app.project_generation,app.mixer_reset_serial)
        reset=context!=self.mixer_context
        if reset:
            app.mixer_peaks={}
            self.mixer_context=context
        watch = app.mixer_watch() if app.page == 'MIXER' else None
        bus = app.plugin_bus() if app.page == 'PLUGIN' else None
        if watch != self.watch or reset:
            self.watch = watch
            audio.command('mixer_watch '+(f'{watch[0]} {watch[1]}' if watch else '-1 0'))
            app.mixer_levels = {}
            app.mixer_master = (0, 0)
            self.status_due = 0
        if bus != self.latency_bus:
            self.latency_bus = bus
            app.plugin_latency_ms = 0
            self.status_due = 0
        if now >= self.status_due:
            if watch: audio.command(f'mixer_status {watch[0]} {watch[1]}')
            if bus is not None: audio.command(f'plugin_latency {bus}')
            self.status_due = now+.1

    def receive(self, app, event):
        if event['kind'] == 'mixer_meter':
            if self.watch and event['first'] == self.watch[0] and len(event['levels']) == self.watch[1]:
                app.mixer_levels = {event['first']+i: tuple(values) for i, values in enumerate(event['levels'])}
                # Native mixer_status exchanges the selected buses before Master;
                # when watching Master itself, its first returned level is authoritative.
                from app.layout import MASTER
                app.mixer_master = app.mixer_levels.get(MASTER,tuple(event['master']))
                for bus,values in (*app.mixer_levels.items(),(MASTER,app.mixer_master)):
                    previous=app.mixer_peaks.get(bus,(0,0))
                    app.mixer_peaks[bus]=tuple(max(old,new) for old,new in zip(previous,values))
            return True
        if event['kind'] == 'plugin_latency':
            if event['bus'] == self.latency_bus and event['rate'] > 0:
                app.plugin_latency_ms = event['frames']*1000/event['rate']
            return True
        return False


def meter_height(peak, maximum=20):
    if not math.isfinite(peak) or peak <= 0:
        return 0
    return max(0, min(maximum, round((20*math.log10(peak)+48)/48*maximum)))
