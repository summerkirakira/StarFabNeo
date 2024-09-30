#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

pushd $DIR/.. &> /dev/null || exit

echo "Clearing old briefcase environment"
rm -rf windows/msi/StarFab/src/app/*
rm -rf windows/msi/StarFab/src/app_packages/*

echo "Updating briefcase"
bc=$(./make/briefcase update 2>&1)
if [ $? != 0 ]; then
  echo $bc
  exit 1
fi

mkdir -p windows/msi/StarFab/src/app/
cp -R ../../frameworks/scdatatools/scdatatools windows/msi/StarFab/src/app/starfab/contrib/

rm -rf windows/msi/StarFab/src/app_packages/scdatatools* &> /dev/null
rm -rf windows/msi/StarFab/src/app_packages/starfab* &> /dev/null

mkdir windows/archive &> /dev/null
mv windows/StarFab* windows/archive/ &> /dev/null
./make/briefcase package

popd &> /dev/null || exit
