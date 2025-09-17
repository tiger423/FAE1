
Replace your_username with the actual username you want to grant privileges to. 

The -a flag ensures that the user is added to the sudo group without removing them from any other groups, and -G specifies the group

After adding the user to the sudo group, they can execute commands with root privileges by preceding them with sudo. For example:


# Create virtual environment

python3 -m venv ssd_env

source ssd_env/bin/activate

# Install packages in venv

pip install psutil pandas

# Run with venv python (deactivate first)

deactivate

sudo ssd_env/bin/python ssd_test_suite.py





FUNCTIONS THAT COULD WORK WITHOUT ROOT

These functions could work in "read-only" mode:

collect_system_info() - Lines 109-150 (CPU, memory info)

collect_pcie_info() - Line 219 (lspci works without root)

System monitoring and CSV logging

RECOMMENDED APPROACH

For Testing:

bash

# Option 1: Quick system-wide install

sudo pip3 install psutil pandas

sudo python3 ssd_test_suite.py

# Option 2: If you have conda/virtual environments

sudo /path/to/your/python ssd_test_suite.py

For Production:

bash

# Create dedicated environment

python3 -m venv /opt/ssd_test

sudo /opt/ssd_test/bin/pip install psutil pandas

sudo /opt/ssd_test/bin/python /path/to/ssd_test_suite.py

VERIFY PACKAGE INSTALLATION

bash

# Check if packages are visible to sudo

sudo python3 -c "import psutil, pandas; print('Packages available')"
