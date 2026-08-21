set -eu
cd /tmp
rm -rf gnb && mkdir gnb && cd gnb

echo "  downloading..."
curl -sSL -m 300 -o GB.zip https://download.geonames.org/export/dump/GB.zip
python3 - <<'PY'
import zipfile, json, io

# GeoNames columns (tab separated, no header):
# 0 id 1 name 2 ascii 3 alt 4 lat 5 lon 6 fclass 7 fcode 8 country ...
# 14 population 15 elevation 16 dem 17 tz 18 modified
#
# Keep populated places (P) and the named high ground people actually navigate
# by (T: peaks, hills, mountains). Everything else — farms, post boxes, bus
# stops — is noise at the resolution this is used at, and each entry costs a
# haversine on every lookup.
KEEP_T = {"MT", "PK", "HLL", "MTS", "RDGE", "PASS", "VAL", "CLF"}
rows = []
with zipfile.ZipFile("GB.zip") as z:
    with z.open("GB.txt") as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            c = line.rstrip("\n").split("\t")
            if len(c) < 15:
                continue
            fclass, fcode = c[6], c[7]
            if fclass == "P":
                pass
            elif fclass == "T" and fcode in KEEP_T:
                pass
            else:
                continue
            try:
                lat, lon = float(c[4]), float(c[5])
                pop = int(c[14] or 0)
            except ValueError:
                continue
            rows.append([c[1], round(lat, 5), round(lon, 5), pop, fcode])

# Sorted by latitude so a lookup can binary-search a narrow band instead of
# scanning all of Britain for every fix.
rows.sort(key=lambda r: r[1])
with open("/tmp/gnb/places.json", "w", encoding="utf-8") as out:
    json.dump(rows, out, ensure_ascii=False, separators=(",", ":"))
print(f"  kept {len(rows)} places")
PY
ls -lh /tmp/gnb/places.json | awk '{print "  built " $5}'
