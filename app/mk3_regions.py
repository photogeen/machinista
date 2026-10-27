"""Dirty RGB565 rectangles: comparisons/slices use native byte operations."""
WIDTH=480
STRIDE=WIDTH*2

def common(a,b,suffix=False):
    lo,hi=0,len(a)
    while lo<hi:
        n=(lo+hi+1)//2
        equal=(a[-n:]==b[-n:]) if suffix else (a[:n]==b[:n])
        if equal:lo=n
        else:hi=n-1
    return lo

def regions(previous,pixels):
    if len(pixels)!=STRIDE*272:raise ValueError('Invalid MK3 frame size')
    if previous is None:return [(0,0,480,272,pixels)]
    if len(previous)!=len(pixels):raise ValueError('Invalid previous MK3 frame')
    bounds=[]
    for top in range(0,272,16):
        end=min(272,top+16)
        if pixels[top*STRIDE:end*STRIDE]==previous[top*STRIDE:end*STRIDE]:continue
        left,right=480,0
        for y in range(top,end):
            a=pixels[y*STRIDE:(y+1)*STRIDE];b=previous[y*STRIDE:(y+1)*STRIDE]
            if a==b:continue
            left=min(left,common(a,b)//2)
            right=max(right,480-common(a,b,True)//2)
        left=left//2*2;right=min(480,(right+1)//2*2)
        if bounds and bounds[-1][0]==left and bounds[-1][2]==right and bounds[-1][3]==top:
            bounds[-1]=(left,bounds[-1][1],right,end)
        else:bounds.append((left,top,right,end))
    return [(x,y,right-x,end-y,b''.join(pixels[row*STRIDE+x*2:row*STRIDE+right*2] for row in range(y,end))) for x,y,right,end in bounds]
