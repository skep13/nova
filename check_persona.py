"""Guard against the escape mangling that has now broken this file twice.

A bash heredoc collapsed a doubled backslash, turning the JS literal
'...offer.\n\n' into a string containing a real newline -- which is an
unterminated string literal and would have taken the whole page down. It looked
fine in a diff. So it is checked mechanically instead.
"""
import persona as P

backslash_n = chr(92) + "n"
assert backslash_n not in P.PERSONA, "literal backslash-n leaked into the persona"
assert "nothing to offer." + chr(10) + chr(10) in P.PERSONA, "patched line wrong"
paras = P.PERSONA.count(chr(10) + chr(10)) + 1
assert paras >= 10, f"paragraph breaks lost: only {paras}"
print(f"  persona intact: {len(P.PERSONA)} chars, {paras} paragraphs, no stray escapes")
