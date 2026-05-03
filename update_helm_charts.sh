#!/bin/bash

package_name=$1
version=$(cat charts/$package_name/Chart.yaml | grep "version:" | awk '{print $2}')
cd helm_charts/

helm package ../charts/$package_name

echo "Version: $version"

git add $package_name-$version.tgz
git commit -m "Update helm chart $package_name to version $version"
git push

cd /tmp 

git clone https://github.com/minnelab/MAIA.git
cd MAIA
git checkout master
git pull
git checkout helm-charts
git pull

git restore --source master -- helm_charts/$package_name-$version.tgz
cd helm_charts
helm repo index ..

git add .
git add ..
#git diff
git commit -m "Update helm charts from master branch"
echo "Changed files in the commit:"
git show --name-only --pretty="" HEAD
git push

# helm repo add maia https://minnelab.github.io/MAIA/