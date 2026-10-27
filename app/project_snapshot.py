"""Independent undo snapshots without deepcopying immutable pattern booleans."""
import copy

def project_snapshot(project):
    result=copy.deepcopy({k:v for k,v in project.items() if k!='groups'})
    result['groups']=[]
    for group in project['groups']:
        saved=copy.deepcopy({k:v for k,v in group.items() if k!='patterns'})
        saved['patterns']=[[lane.copy() for lane in pattern] for pattern in group['patterns']]
        result['groups'].append(saved)
    return result
