#!/bin/bash

rm package.zip

mkdir package
cp mods/manifest.json package

mkdir package/overrides
cp -r config defaultconfigs kubejs packmenu patchouli_books simple-rpc package/overrides

cd package
zip -rq ../package.zip *
cd ../
rm -r package
