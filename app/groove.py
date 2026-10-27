"""Hierarchical Sound/Group/Master groove from amount, cycle and inversion."""
CYCLES=('1/1','1/2','1/4','1/8','1/16')
def settings(target,amount=0):return dict({'amount':amount,'cycle':'1/4','invert':False},**target.get('groove',{}))
def shifted(tick,length,groove):
    span=384/int(groove['cycle'].split('/')[1]);half=span/2
    block,phase=divmod(tick,span);delay=span/4*groove['amount']/100*(-1 if groove['invert'] else 1)
    value=phase*(half+delay)/half if phase<half else half+delay+(phase-half)*(half-delay)/half
    return min(length-1,max(0,round(block*span+value)))
def validate_groove(project):
    for target in [project]+project['groups']+[p for g in project['groups'] for p in g['pads']]:
        g=settings(target)
        if type(g['amount']) is not int or not 0<=g['amount']<=100 or g['cycle'] not in CYCLES or type(g['invert']) is not bool:raise ValueError('invalid groove')
class Groove:
    def groove_position(self,group,pad,tick,length):
        for target,default in ((self.project,self.timing()['swing']),(self.project['groups'][group],0),(self.project['groups'][group]['pads'][pad],0)):
            tick=shifted(tick,length,settings(target,default))
        return tick
    def groove_button(self,name,pressed):
        if self.page!='GROOVE':return False
        if pressed and name in ('NAV LEFT','NAV RIGHT'):self.groove_field=max(0,min(2,self.groove_field+(-1 if name=='NAV LEFT' else 1)));return True
        return False
    def groove_rotate(self,delta):
        if self.page!='GROOVE':return False
        self.remember();target=self.plugin_target();g=target.setdefault('groove',settings(target,self.timing()['swing'] if self.control_level==0 else 0))
        key=('amount','cycle','invert')[self.groove_field]
        if key=='amount':g[key]=max(0,min(100,g[key]+delta))
        elif key=='cycle':g[key]=CYCLES[max(0,min(4,CYCLES.index(g[key])+delta))]
        else:g[key]=delta>0
        if self.control_level==0:self.timing()['swing']=g['amount']
        return True
