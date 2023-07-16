import requests as r
import zipfile, io
import os
import json as j
import urllib.parse
import string, random
import psutil
import subprocess
import multiprocessing
from time import sleep
from threading import Thread, Event


def id_generate(size=6, chars=string.ascii_uppercase + string.digits):
  return ''.join(random.choice(chars) for i in range(size))


class StoppableThread(Thread):
  """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

  def __init__(self, *args, **kwargs):
    super(StoppableThread, self).__init__(*args, **kwargs)
    self._stop_event = Event()

  def stop(self):
    self._stop_event.set()

  def stopped(self):
    return self._stop_event.is_set()


class ServerPoller:

  def __init__(self, config="config.json", project_dir="projects"):
    self.url = ""
    self.client = ""
    self.projects = project_dir
    self.config = config
    self.polling = []
    self.running = {}
    self.threads = {}

  def loadConfig(self):
    f = open(self.config, 'r')
    json = j.load(f)
    print(json)
    self.url = json["url"]
    self.client = json["client"]
    return True

  def checkFile(self, filepath):
    return os.path.isfile(filepath)

  def checkDir(self, filepath):
    return os.path.isdir(filepath)

  def initConfig(self):
    print('[1] Starting init config')
    if (self.checkFile(self.config)):
      self.loadConfig()
      print('[2] Loaded config')
      if (self.checkDir(self.projects)):
        return True
      else:
        print(f'[*] Need to create project dir: {self.projects}')
        os.mkdir(self.projects)
    else:
      url = input('Enter url of the server: ')
      client = id_generate(25)
      f = open(self.config, 'w')
      f.write(j.dumps({"url": url, "client": client}))
      f.close()
      self.loadConfig()

  def should_send_log_to_server(self):
    pass

  def send_log_to_server(self, log_data, projectName):
    url = f'{self.url}/upload/logs?project={projectName}'
    device_id = self.client
    #with open(log_file_path, 'r') as log_file:
    #  log_data = log_file.read()
    payload = {
      'device_id': device_id,
      'project_name': projectName,
      'log_data': log_data
    }
    response = r.post(url, data=payload)
    if response.status_code == 200:
      print(f'[>] Log file for [{projectName}] was successfully sent.')
    else:
      print(f'[<] Error in sending [{projectName}] logs.')

  def execute_bash_script(self, script_path, log_file_path, projectName):
    process = subprocess.Popen(['bash', script_path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    for line in process.stdout:
      self.send_log_to_server(line.decode(), projectName)

  def startProject(self, projectName):
    script_path = f'{self.projects}/{projectName}/main.sh'
    log_file_path = f'{self.projects}/{projectName}/logFile.log'
    thread = {
      projectName:
      multiprocessing.Process(target=self.execute_bash_script,
                              args=(script_path, log_file_path, projectName))
    }
    self.running[projectName] = thread[projectName]
    self.running[projectName].start()
    self.running[projectName].join()

  def start(self):
    items = os.listdir(self.projects + '/')
    for item in items:
      if os.path.isdir(self.projects + '/' + item):
        if (self.checkFile(self.projects + '/' + item + '/main.sh')):
          print(
            f'[>] Project [{item}] is available. Checking conflicts and starting it if not conflicts.'
          )
          self.threads[item] = StoppableThread(target=self.startProject,
                                               args=(item, ))
          self.threads[item].start()
        else:
          print(
            f'[<] Project [{item}] is empty. Waiting for archive of it to start.'
          )
          self.polling.append(item)

  def send_command(self, id, project, message):
    print(f'{project} sent {message}')
    myobj = {'id': id, 'message': (message)}
    r.post(f'{self.url}/api/devices/poll', data=myobj)

  def processCommands(self):
    commands = r.get(
      f'{self.url}/api/devices/poll?device={self.client}&action=get_commands')
    commands_result = commands.text
    commands_result_json = j.loads(commands_result)
    command = commands_result_json["commands"]
    for com in command:
      if (com["command"] == 'stop'):
        if (self.running[com["project"]]):
          psProcess = psutil.Process(pid=self.running[com["project"]].pid)
          psProcess.suspend()
          self.send_command(com["id"], com["project"], 'Stopped successfully')
      if (com["command"] == 'start'):
        if (self.running[com["project"]]):
          psProcess = psutil.Process(pid=self.running[com["project"]].pid)
          psProcess.resume()
        else:
          item = com["project"]
          if (self.checkFile(self.projects + '/' + item + '/main.sh')):
            print(
              f'[>] Project [{item}] is available. Checking conflicts and starting it if not conflicts.'
            )
            if (self.threads[item]):
              psProcess = psutil.Process(pid=self.running[com["project"]].pid)
              psProcess.suspend()
              self.threads[item].stop()
              print('Stopped running thread')
            print('Started thread')
            self.threads[item] = StoppableThread(target=self.startProject,
                                                 args=(item, ))
            self.threads[item].start()
        self.send_command(com["id"], com["project"], 'Started successfully')
      if (com["command"] == 'download'):
        if (self.checkDir(self.projects + '/' + com["project"]) == False):
          os.mkdir(self.projects + '/' + com["project"])
        archive = r.get(
          f'{self.url}/api/download/project?project={com["project"]}',
          allow_redirects=True)
        z = zipfile.ZipFile(io.BytesIO(archive.content))
        z.extractall(self.projects + '/' + com["project"])
        self.send_command(com["id"], com["project"],
                          'Downloaded and unarchived project')
        item = com["project"]
        if (self.checkFile(self.projects + '/' + item + '/main.sh')):
          print(
            f'[>] Project [{item}] is available. Checking conflicts and starting it if not conflicts.'
          )
          if (self.threads[item]):
            psProcess = psutil.Process(pid=self.running[com["project"]].pid)
            psProcess.suspend()
            self.threads[item].stop()
            print('Stopped running thread')
          print('Started thread')
          self.threads[item] = StoppableThread(target=self.startProject,
                                               args=(item, ))
          self.threads[item].start()
        else:
          print(
            f'[<] Project [{item}] is empty. Waiting for archive of it to start.'
          )
          self.polling.append(item)

  def serverPoll(self):
    while True:
      print(f'[*] Polling server at > {self.url}')
      self.processCommands()
      #self.checkProjects()
      sleep(5)


server = ServerPoller()
server.initConfig()
server.start()

server.serverPoll()
