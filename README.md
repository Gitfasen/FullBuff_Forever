# FullBuff

FullBuff is a World of Warcraft: Forever addon. Its buff database is generated
from WoW DB2 data by a Python build pipeline in `tools/`.

Build the database (pipeline entry point, implemented in a later task):

    python tools/build.py --build 1.60.1.70338

Run the tests with:

    pytest

Licensed under GPL-3.0.
