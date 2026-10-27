"""Reachable controller workspaces covered by Fokus V2.

This is an audit inventory, not a second navigation system. Existing engine
handlers remain authoritative for actions, ranges, persistence and Undo.
"""
from app.settings_menu import SETTING_PAGES

WORKFLOWS={
 'Control':('PAD','CHANNEL','INPUT','GROOVE','MACRO','MACRO ASSIGN','SAMPLER','PLUGIN','PLUGIN SLOTS','PARAM NAV'),
 'Browser / Plugins':('BROWSE','PLUGIN BROWSE','PLUGIN MOVE','PLUGIN SC'),
 'Sampling':('AUTOSAMPLER','SAMPLING','SAMPLING NAV','SAMPLE EDIT','CHOP','ZONE','STRETCH','SLICE TARGET','SAMPLE DELETE','AUDIO LOOP','BOUNCE TO PAD'),
 'Performance':('LIVE FX','PAD CONFIG','NOTE REPEAT','ARP','GROUP','SELECT','DUPLICATE','MUTE','SOLO'),
 'Sequencer':('STEP','PATTERN','PATTERN GRID','GRID EDIT','EVENT','OPTIONS','RECORD SETTINGS','RECORD PREPARE','MIDI TRACK','VIEW NAV'),
 'Arrangement':('SCENE','SCENE OPTIONS','SONG','SONG AUTO'),
 'Mixer':('MIXER',),
 'Projects / Export':('PROJECT','PROJECT LOAD','PROJECT MANAGE','PROJECT NAME','PRESET LOAD','MISSING SAMPLES','RELINK RESULTS','RELINK BROWSE','SAMPLE RAM','EXPORT','EXPORT DONE','CONFIRM'),
 'Compatibility':('KEYBOARD','CHORD','NAVIGATE','FX','PROCESS','LENGTH'),
 'Settings':('SETTINGS',)+tuple(dict.fromkeys(SETTING_PAGES)),
}
PAGES=tuple(dict.fromkeys(p for pages in WORKFLOWS.values() for p in pages))
