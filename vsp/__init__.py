"""vsp — support package for the viral script pipeline.

Stdlib-only, Python 3.9+. The entry points stay where they always were
(pipeline.py, viral_script_maker.py, make_shotlist.py, research_bridge.py);
this package holds the pieces they share: config/paths, the fixture DB,
the quality rubric, seeding, timing, routing, rules, exports and the run
manifest.
"""

__version__ = "2.0.0"
