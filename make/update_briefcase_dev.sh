#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"


pushd $DIR/.. &> /dev/null || exit

rm -rf windows/msi/StarFab/src/app/*
poetry run briefcase update $@
mkdir -p windows/msi/StarFab/src/app/
cp -R ../../frameworks/scdatatools/scdatatools windows/msi/StarFab/src/app/starfab/contrib/

popd &> /dev/null || exit
