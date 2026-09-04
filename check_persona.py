"""Guard against the escape mangling that has now broken this file twice.

A bash heredoc collapsed a doubled backslash, turning the JS literal
'...offer.\n\n' into a string containing a real newline -- which is an
unterminated string literal and would have taken the whole page down. It looked
fine in a diff. So it is checked mechanically instead.
"""
import persona as P

# Both personas are checked: the short one ships to small models and is
# assembled by the same fragile string concatenation.

backslash_n = chr(92) + "n"
assert backslash_n not in P.PERSONA, "literal backslash-n leaked into the persona"
# Re-pointed at the current persona. The specific sentence does not matter;
# what matters is that SOME paragraph break survived the JS-to-Python trip,
# which is exactly what the mangling destroys.
assert "offering more help." in P.PERSONA, "the persona tail is missing"
paras = P.PERSONA.count(chr(10) + chr(10)) + 1
assert paras >= 10, f"paragraph breaks lost: only {paras}"
print(f"  persona intact: {len(P.PERSONA)} chars, {paras} paragraphs, no stray escapes")

assert backslash_n not in P.PERSONA_SHORT, "literal backslash-n in the short persona"
assert P.PERSONA_SHORT.count(chr(10) + chr(10)) + 1 >= 6, "short persona lost its breaks"
print(f"  persona {len(P.PERSONA)} chars / {paras} paragraphs, "
      f"short {len(P.PERSONA_SHORT)} chars - no escape mangling")
