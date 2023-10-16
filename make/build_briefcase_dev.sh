#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

pushd $DIR/.. &> /dev/null || exit

OLD_PATH=$PATH

# setup build venv
deactive &> /dev/null
mkdir build &> /dev/null
rm -rf build/venv &> /dev/null
echo "Setting up build virtualenv"
poetry run python -m venv build/venv
. build/venv/Scripts/activate
export PATH="$PATH:$OLD_PATH"
which python
python -m pip install -U pip briefcase==0.3.7 &> /dev/null
which briefcase

echo "Clearing old briefcase environment"
rm -rf windows/msi/StarFab/src/app/*
rm -rf windows/msi/StarFab/src/app_packages/*

echo "Updating briefcase"
bc=`briefcase update -d`
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
briefcase build

popd &> /dev/null || exit
