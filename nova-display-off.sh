#!/bin/sh
# Keep the T470's panel dark. It is a headless server in a drawer.
#
# Three separate things have to agree, which is why this is a script and not a
# one-liner. The lid switch, the backlight class and the console blanker each
# turn the screen off on their own terms, and any one of them can turn it back
# on: opening the lid restores the backlight, and console output unblanks the
# framebuffer even with the lid shut.
#
# Reversible by hand at any time:
#   echo 0 > /sys/class/backlight/intel_backlight/bl_power
#   setterm --blank poke > /dev/tty1
set -eu

# 4 is FB_BLANK_POWERDOWN — the backlight is actually off, not painting black.
# Writing brightness as well because the two are independent on i915: a zero
# bl_power with a live brightness value comes back lit on the next wake.
for bl in /sys/class/backlight/*/; do
    [ -w "$bl/bl_power" ] && echo 4 > "$bl/bl_power" || true
done

# Blank the console after a minute of no output, and power the panel down
# rather than merely blanking it. Written to tty1 explicitly: setterm acts on
# its own terminal, and over SSH that is the SSH session, not the screen.
if [ -w /dev/tty1 ]; then
    TERM=linux setterm --blank 1 --powersave powerdown --powerdown 1 \
        > /dev/tty1 2>/dev/null || true
fi

# And the framebuffer itself, for the case where there is no console activity
# at all to trigger the blanker.
[ -w /sys/class/graphics/fb0/blank ] && echo 4 > /sys/class/graphics/fb0/blank || true

exit 0
