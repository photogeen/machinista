#!/usr/bin/env python3
"""Import user-supplied OB-Xd FXB/FXP, Dexed SYX or RaffoSynth DAT/JSON banks into a Machinista installation."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.plugin_bank_import import import_bank,MAX_SIZE
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('file',type=Path);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--profile',default='obxd')
a=p.parse_args()
try:
    with a.file.open('rb') as f:data=f.read(MAX_SIZE+1)
    print(json.dumps(import_bank(a.root,a.profile,a.file.name,data),indent=2))
except (OSError,ValueError) as e:p.exit(1,str(e)+'\n')
