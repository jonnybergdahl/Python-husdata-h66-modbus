#!/usr/bin/env zsh
setopt rm_star_silent

pandoc README.md -o README.rst
sphinx-build -b html docs/source docs/build
rm -rf ~/Developer/jonnybergdahl/jonnybergdahl.github.io/husdata-h66-modbus/*
cp -r docs/build/ ~/Developer/jonnybergdahl/jonnybergdahl.github.io/husdata-h66-modbus
touch ~/Developer/jonnybergdahl/jonnybergdahl.github.io/husdata-h66-modbus/.nojekyll

pushd ~/Developer/jonnybergdahl/jonnybergdahl.github.io || exit
git checkout main
git pull
git add husdata-h66-modbus
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "Update husdata-h66-modbus docs"
  git push
else
   echo "Branch main is up to date,nothing to do."
fi
popd || exit

rm -rf dist
python3 -m build
twine upload dist/*
