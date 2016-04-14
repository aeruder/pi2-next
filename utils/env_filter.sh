#!/usr/bin/env bash
TMPFILE="`mktemp`"
TMPFILE2="`mktemp`"

trap "rm -f $TMPFILE $TMPFILE2" EXIT

cat > "$TMPFILE"

cpp -nostdinc "$@" -x assembler-with-cpp -o "$TMPFILE2" "$TMPFILE"

cat "$TMPFILE2" |
sed -e 's/\(^\|[^\\]\)#.*// ; s/\\#/#/g' |
grep -v '^[ 	]*$' |
perl -pe 's/\\ *\n//m'

