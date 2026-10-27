"""Small monochrome plots from real control values; no audio work or fake meters."""
import math


def arrow(c,x,y,end):
    c.line(x,y,end,y);c.line(end-3,y-3,end,y);c.line(end-3,y+3,end,y)


def folder(c,x,y,selected=False):
    ink=c.bg if selected else c.ink
    c.rect(x,y,5,2,ink);c.rect(x,y+2,10,6,ink,False)


def response(c,section,values,x=5,y=26,w=None,h=18):
    from app.sampler import DEFAULTS
    v={**DEFAULTS,**values};w=w or c.w-10
    def plot(points):
        for a,b in zip(points,points[1:]):c.line(*a,*b)
    if section in (1,3):
        kind=v['type'] if section==1 else 'AHD'
        if kind=='ONESHOT':
            c.text(x,y+5,'ONE SHOT',w,font='bold5');return
        prefix='mod_' if section==3 else ''
        attack=float(v[prefix+'attack']);decay=float(v[prefix+'decay'])
        hold=float(v['hold']) if kind=='AHD' and section==1 else 0
        release=float(v['release']) if kind=='ADSR' else 0
        sustain=float(v['sustain'])/100 if kind=='ADSR' else 0
        # Keep sustain visible; time proportions represent the actual settings.
        plateau=max(20,(attack+decay+release)*.25) if kind=='ADSR' else hold
        total=max(1,attack+decay+release+plateau)
        xa=x+round(attack/total*(w-1));xd=xa+round(decay/total*(w-1))
        xs=min(x+w-1,xd+round(plateau/total*(w-1)))
        base=y+h-1;top=y;sy=base-round(sustain*(h-1))
        if kind=='AHD':
            xh=xa+round(hold/total*(w-1));points=[(x,base),(xa,top),(xh,top),(x+w-1,base)]
        else:points=[(x,base),(xa,top),(xd,sy),(xs,sy),(x+w-1,base)]
        plot(points)
    elif section==2:
        from app.sampler import cutoff_position
        anchor=cutoff_position(v['cutoff'])
        points=[]
        for i in range(w):
            phase=i/max(1,w-1);a=1/(1+math.exp(max(-50,min(50,(phase-anchor)*20))))
            if v['filter']=='HP2':a=1-a
            if v['filter'] in ('BP2','EQ'):a=math.exp(-((phase-anchor)*8)**2)
            if v['filter']=='OFF':a=.5
            points.append((x+i,y+h-1-round(a*(h-1))))
        plot(points);xx=x+round(anchor*(w-1));c.line(xx,y,xx,y+h-1)
    elif section==4:
        points=[];phase=float(v['lfo_phase'])/360;cycles=2
        for i in range(w):
            t=(i/max(1,w-1)*cycles+phase)%1;shape=v['lfo_shape']
            # RANDOM is explicitly a shape symbol; never pretend to show DSP samples.
            a=math.sin(t*math.tau) if shape=='SINE' else 1-4*abs(t-.5) if shape=='TRI' else 1 if shape=='RECT' and t<.5 else -1 if shape=='RECT' else 2*t-1 if shape=='SAW' else (0,.7,-.4,1,-.8,.3)[min(5,int(t*6))]
            points.append((x+i,y+round((1-a)*(h-1)/2)))
        plot(points)
    elif section==5:
        for i,key in enumerate(('vel_volume','vel_cutoff','vel_start')):
            xx=x+i*w//3;c.line(xx,y+h-1,xx+w//3-5,y+h-1-round(abs(float(v[key]))/100*(h-1)))
    else:
        n=v['polyphony'];n=8 if isinstance(n,str) else int(n)
        # A compact voice strip leaves breathing room above the parameter footer.
        strip_w=max(32,w*3//4);strip_x=x+(w-strip_w)//2
        strip_h=max(3,(h-5)//2)
        for i in range(min(16,n)):
            xx=strip_x+i*strip_w//16;c.rect(xx,y+2,max(1,strip_w//16-2),strip_h,c.ink,False)
        c.text(x,y+strip_h+4,str(v['polyphony'])+' VOICES',w,font='bold5')


def route(c,data,y=28):
    src,dst=data;w=c.w
    left=max(36,(w-28)//2);right=w-left-24
    c.rect(4,y,left,13,c.ink,False);c.text(7,y+4,src,left-6,font='bold5')
    arrow(c,5+left,y+6,16+left)
    c.rect(18+left,y,right,13,c.ink,False);c.text(21+left,y+4,dst,right-6,font='bold5')


def chain(c,items,selected):
    first=max(0,selected-1)
    for i,(label,bypass) in enumerate(items[first:first+3]):
        index=first+i;y=24+i*7;chosen=index==selected
        if chosen:c.rect(3,y,c.w-6,7)
        ink=c.bg if chosen else c.ink
        c.rect(5,y+2,3,3,ink,not bypass)
        c.text(12,y+1,f'{index+1} '+label,c.w-17,ink=ink,font='bold5')


def bars(c,values):
    for i,(label,value) in enumerate(values[:3]):
        y=25+i*7;c.text(4,y,label,88)
        c.rect(97,y,151,5,c.ink,False);c.rect(99,y+2,round(max(0,min(1,value))*147),1)
