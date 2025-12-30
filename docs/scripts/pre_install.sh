cp README.md docs/source/README.md
mkdir -p docs/source/apidocs/tutorials/Admin
cp GPU_Booking_System.md docs/source/apidocs/tutorials/Admin/GPU_Booking_System.md
cp GPU-Booking-System.png docs/source/apidocs/tutorials/Admin/GPU-Booking-System.png
cp Deploy_Custom_App.md docs/source/apidocs/tutorials/Admin/Deploy_Custom_App.md
cp Deploy_MAIA_Namespace_from_CLI.md docs/source/apidocs/tutorials/Admin/Deploy_MAIA_Namespace_from_CLI.md
cp CIFS/README.md docs/source/apidocs/tutorials/Admin/README_CIFS.md
cp -r dashboard/docs docs/source/apidocs/tutorials/Dashboard
cp -r docker/MAIA-Workspace/Tutorials docs/source/apidocs/tutorials/MAIA-Workspace
mkdir -p docs/source/apidocs/tutorials/Installation
cp ansible/MAIA/Installation/README.md docs/source/apidocs/tutorials/Installation/README.md
python docs/scripts/generate_tutorials_rst.py
python docs/scripts/generate_scripts_rst.py