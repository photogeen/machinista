"""Advance on scheduled deadlines, dropping stale sound events after a stall."""
def advance_clock(app, deadline, now):
    interval=app.clock_interval()
    overdue=now-deadline
    # Ordinary Linux/UI jitter must not silently delete musical events. Preserve
    # notes up to25ms late; after a larger stall retain the anti-burst policy.
    stalled=overdue>0.025
    stats=getattr(app,'clock_stats',None)
    if stats is None:app.clock_stats=stats={'max_late_ms':0.,'late_cycles':0,'dropped_ticks':0}
    stats['max_late_ms']=max(stats['max_late_ms'],max(0,overdue)*1000)
    if overdue>0.01:stats['late_cycles']+=1
    while deadline<=now+1e-9 and (app.playing or app.count_remaining):
        emit=not stalled or deadline>=now-0.01
        if not emit:stats['dropped_ticks']+=1
        app.clock_tick(deadline,emit=emit)
        deadline+=interval
    if not (app.playing or app.count_remaining):deadline=now
    return deadline, overdue>0.1
