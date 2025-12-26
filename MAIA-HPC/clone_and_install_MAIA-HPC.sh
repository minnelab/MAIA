git clone -n --depth=1 --filter=tree:0 \
  https://github.com/minnelab/MAIA.git
cd MAIA
git sparse-checkout set --no-cone /MAIA-HPC
git checkout
cd MAIA-HPC
sudo ./install.sh