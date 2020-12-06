#!/bin/sh

git clone https://github.com/ajaxorg/ace-builds/

QRC=./embed.qrc
echo '<!DOCTYPE RCC>' > $QRC
echo '<RCC version="1.0">' >> $QRC
echo '  <qresource>' >> $QRC

# Each file in the Ace source folder has to be added in individually
for a in $(find ace-builds/src-min-noconflict -d)
do
    # if this is not a folder
    if [ ! -d "$a" ]; then
        echo '      <file>'$a'</file>' >> $QRC
    fi
done

echo '  </qresource>' >> $QRC
echo '</RCC>' >> $QRC

pyside2-rcc embed.qrc -o embedrc.py
