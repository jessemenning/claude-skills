#!/usr/bin/env python3
"""Replace ${VAR} placeholders in a Feldera program so the SQL compiler accepts it.

Demo programs keep connector credentials as ${FL_*} tokens that init.sh substitutes.
The compiler validates connector JSON, so ports must become a number and the rest a string.

Usage: substitute_vars.py <program.sql>  (writes the substituted SQL to stdout)
"""
import re
import sys

sql = open(sys.argv[1]).read()
sys.stdout.write(re.sub(r"\$\{([^}]*)\}", lambda m: "55555" if "PORT" in m.group(1).upper() else "x", sql))
